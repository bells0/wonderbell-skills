---
name: codex-bridge
description: >-
  Read, search, and communicate with local OpenAI Codex CLI/App sessions. Use
  whenever the user asks to inspect Codex conversation history, sync context
  from a Codex thread, search what was discussed in Codex, continue/drive an
  existing Codex session via `codex exec resume`, or delegate a new task to
  Codex via `codex exec`.
---

# Codex Bridge

Fixed, repeatable workflow for reading local Codex sessions and (when explicitly requested) driving Codex threads through the underlying `codex` CLI.

All operations go through the bundled zero-dependency helper script:
- [scripts/codex_bridge.py](./scripts/codex_bridge.py)

## Data Sources

By default the script reads `$CODEX_HOME` (falling back to `~/.codex`):
- **Index**: latest `state_*.sqlite` (`threads` table), with automatic fallback to `session_index.jsonl` and `sessions/**/*.jsonl`.
- **Transcripts**: each thread's `rollout_path` JSONL under `sessions/YYYY/MM/DD/rollout-*.jsonl` (and `archived_sessions/` when requested).
- **Concurrency detection**: combines `thread-writer-locks/<session_id>.lock` (`[LOCKED]` when loaded in Codex App/TUI) with rollout tail inspection (`[RUNNING]` when a turn is actively executing).

> Because `$CODEX_HOME` lives outside the project workspace and `codex exec` requires Codex credentials + network access, running the script usually requires unsandboxed execution approval.

## Operating Rules

1. **Read-only by default**: When the user asks to check, summarize, or sync from Codex, use only `list`, `search`, and `read`. Never call `send` or `start` unless the user explicitly asks to message, resume, or drive Codex.
2. **Progressive context loading**:
   - First locate the target session with `list` or `search`.
   - Next run `read <id> --last-turns 10` (or `--final-only`) to inspect recent conclusions without flooding context.
   - Only add `--include-tools`, `--last-turns 0`, or `--max-chars 0` when deeper tool logs or full history are actually needed.
3. **Safe driving guardrails (`send` / `start`)**:
   - **Client-visible default (`app-server`)**: `start` and `send` default to `--via app-server` (`codex app-server --stdio`), which persists threads with interactive `source="vscode"` so they appear in the Codex Desktop sidebar (unlike legacy `codex exec`, whose `source="exec"` threads are hidden by default). Pass `--via exec` only if you specifically want headless `codex exec` behavior.
   - **Project root matching**: `start` automatically maps a subdirectory `-C` to its registered Codex Desktop project root (from `state_*.sqlite`'s `project_roots`) for `thread.cwd` while keeping the requested subdirectory for the turn, so the new chat appears under the right project in Codex Desktop. Use `projects` to inspect registered roots, or `--exact-cwd` to disable mapping.
   - **Binary, default model & reasoning**: `send` and `start` automatically pick the highest-version local `codex` CLI binary (checking macOS ChatGPT/Codex app bundles, Windows Codex install path, and `PATH`, overridable via `CODEX_BRIDGE_BIN`), select the newest default visible model from `$CODEX_HOME/models_cache.json` (lowest `priority` with `visibility == "list"`), and set reasoning effort to `high`. Override with `-m <model>` or `-r <effort>` only when needed.
   - Default sandbox for Codex execution is `read-only`. Only pass `--sandbox workspace-write` when the user explicitly wants Codex to edit files or run mutating commands. Never use `danger-full-access` unless the user explicitly requests it.
   - Before `send`, confirm the resolved session ID, project `cwd`, and that the thread is **not busy**. The script automatically runs inside the session's recorded `cwd` (when that directory exists) so resuming does not drift the thread's project root, and refuses to send if an active turn or writer lock is detected (`[RUNNING]` / `[LOCKED]`). Do not pass `--force` while Codex App/TUI is actively holding that thread.
   - For multi-line or complex prompts, write the prompt to a temporary file and pass `--prompt-file <file>` (or pipe via stdin with `-`) to avoid shell quoting bugs.

## Standard Commands

Let `SCRIPT` be the path to `scripts/codex_bridge.py` inside this skill directory.
On Windows, if `python3` points to the Microsoft Store stub, invoke the script with a real Python 3 interpreter (e.g., `python`, `py -3`, or `uv run python`).

### 1. List Recent Sessions

```bash
python3 "$SCRIPT" list --limit 15
python3 "$SCRIPT" list --cwd my-repo --limit 10
python3 "$SCRIPT" list --query "auth" --include-archived
```

### 2. Search Across Session Messages

```bash
python3 "$SCRIPT" search "keyword" --days 30 --limit 10
python3 "$SCRIPT" search "deploy" --cwd my-repo
```

### 3. Read a Specific Session

```bash
# Read the latest active session (or latest in a given project)
python3 "$SCRIPT" read --last --cwd my-repo --last-turns 10

# Read by session UUID, UUID prefix, or thread name
python3 "$SCRIPT" read <SESSION_ID_OR_PREFIX> --last-turns 12 --final-only

# Deep read with tool calls and pagination
python3 "$SCRIPT" read <SESSION_ID> --include-tools --offset 0 --limit 30 --max-chars 8000
```

### 4. Resume / Drive an Existing Session

```bash
# Dry-run first when verifying target and flags
python3 "$SCRIPT" send <SESSION_ID> "总结你当前这轮改动和未完成项" --dry-run

# Read-only follow-up question (default --sandbox read-only)
python3 "$SCRIPT" send <SESSION_ID> "总结你当前这轮改动和未完成项"

# Ask Codex to make edits in its session workspace (only when explicitly requested)
python3 "$SCRIPT" send <SESSION_ID> "按计划修复单测并跑一遍验证" --sandbox workspace-write
```

### 5. Start a New Codex Session (Visible in Codex Desktop)

```bash
# List Codex Desktop registered project roots
python3 "$SCRIPT" projects

# Start a client-visible thread in a registered project with an optional name
python3 "$SCRIPT" start "检查当前仓库的构建配置并给出风险清单" -C /path/to/repo --name "构建配置风险排查" --sandbox read-only
```

The command returns the new `Thread ID` (with `source=vscode`), which appears under the matched project in Codex Desktop (refresh/reload the client if it was already open) and can be passed to `read <Thread ID>` or `send <Thread ID>` in follow-up turns.

## Troubleshooting

- **Sandbox / permission error (`Operation not permitted`)**: Re-run the single `python3 "$SCRIPT" ...` command with host access approved so it can read `~/.codex` or invoke `codex exec`.
- **`Refusing to send: session ... currently holds an active writer lock` / `already has an active writer`**: That thread is currently loaded by Codex Desktop App or CLI TUI, which holds an exclusive writer lock. Close/unload that thread (or pick an unlocked session) before calling `send`.
- **Ambiguous target**: Run `list --query <term>` first and pass the exact UUID or unique UUID prefix.
