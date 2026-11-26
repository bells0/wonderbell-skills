---
name: workbuddy-bridge
description: >-
  Read, search, and communicate with local Tencent WorkBuddy Desktop / CodeBuddy
  CLI sessions. Use whenever the user asks to inspect WorkBuddy conversation
  history, sync context from a WorkBuddy session, search what was discussed in
  WorkBuddy, continue/drive an existing WorkBuddy session via `codebuddy -p -r`,
  or start a new non-interactive WorkBuddy/CodeBuddy session via `codebuddy -p`.
---

# WorkBuddy Bridge

Fixed, repeatable workflow for reading local WorkBuddy Desktop sessions (`~/.workbuddy/workbuddy.db` + `projects/<slug>/<session-id>.jsonl`) and (when explicitly requested) sending messages to existing or new sessions via the underlying `codebuddy` CLI.

All operations go through the bundled zero-dependency helper script:
- [scripts/workbuddy_bridge.py](./scripts/workbuddy_bridge.py)

## Data Sources

By default the script reads `$WORKBUDDY_HOME` (falling back to `~/.workbuddy`):
- **Index**: `workbuddy.db` (`sessions`, `spaces`, `session_usage` tables, opened read-only), with automatic fallback to scanning `projects/*/*.jsonl`.
- **Transcripts**: `projects/<encoded-cwd>/<session-id>.jsonl` (with glob fallback across `projects/*/<session-id>.jsonl`).
- **Concurrency detection**: checks `sessions.status` (`working` / `running` -> `[WORKING]`) and recent transcript tail activity (`[ACTIVE]`) before allowing `send`.

> Because `$WORKBUDDY_HOME` lives outside the project workspace and `send`/`start` invoke the `codebuddy` CLI with network access, running the script usually requires unsandboxed execution approval.

## CLI Resolution & Authentication (`send` / `start`)

Read operations (`doctor`, `list`, `search`, `read`) require **no extra installation or login** — they read `~/.workbuddy` directly.

For `send` and `start`, the script resolves the CLI automatically in this order:
1. `$WORKBUDDY_BRIDGE_BIN` (explicit override)
2. Standalone `codebuddy` / `cbc` in `PATH` (`npm install -g @tencent-ai/codebuddy-code`)
3. Bundled WorkBuddy Desktop CLI (`<WorkBuddy>/resources/app.asar.unpacked/cli/bin/codebuddy` + bundled Node + `CODEBUDDY_FORCE_LITE_WB_BUNDLE=1`; checks `$WORKBUDDY_APP_DIR` first, then standard Windows/macOS install locations)

The script sets `CODEBUDDY_CONFIG_DIR=$WORKBUDDY_HOME` (and `CODEBUDDY_INTERNET_ENVIRONMENT=internal` by default, overridable via `--env`) so `--resume` reads and appends directly to WorkBuddy's own session transcripts under `~/.workbuddy/projects/`.

**Authentication options** (WorkBuddy Desktop's Electron login state is not shared with external CLI subprocesses):
- **Option 1 — API Key (works directly with the bundled WorkBuddy CLI, no extra install needed)**:
  Set `CODEBUDDY_API_KEY` (and `CODEBUDDY_INTERNET_ENVIRONMENT=internal` for China edition).
- **Option 2 — Interactive `/login` (requires standalone CLI)**:
  Install `@tencent-ai/codebuddy-code` (on Windows PowerShell use `npm.cmd install -g @tencent-ai/codebuddy-code` if `.ps1` scripts are restricted), then run `python3 "$SCRIPT" login` or:
  ```powershell
  $env:CODEBUDDY_CONFIG_DIR = "$HOME\.workbuddy"
  $env:CODEBUDDY_INTERNET_ENVIRONMENT = "internal"
  codebuddy.cmd
  # complete QR/browser login (or run /login), then /exit
  ```

## Operating Rules

1. **Read-only by default**: When the user asks to check, summarize, or sync from WorkBuddy, use only `doctor`, `list`, `search`, and `read`. Never call `send` or `start` unless the user explicitly asks to message, resume, or drive WorkBuddy.
2. **Progressive context loading**:
   - First locate the target session with `list` or `search`.
   - Next run `read <id> --last-turns 10` (or `--final-only`) to inspect recent conclusions without flooding context.
   - Only add `--include-tools`, `--include-reasoning`, `--last-turns 0`, or `--max-chars 0` when deeper tool logs or full history are actually needed.
3. **Safe driving guardrails (`send` / `start`)**:
   - Default `--mode` is `read-only` (`--permission-mode plan`). Use `--mode text-only` (`--tools ""`) for pure Q&A without tool calls, `--mode edit` (`--permission-mode acceptEdits`) only when the user explicitly wants file edits, and never use `--mode full` (`bypassPermissions -y`) unless explicitly requested.
   - Before `send`, confirm the resolved session ID, project `cwd`, and that the session is **not busy** (`status != working`). The script automatically runs inside the session's recorded `cwd` (when that directory exists) and refuses to send if `[WORKING]` is detected. Do not pass `--force` while WorkBuddy Desktop is actively executing that session.
   - Pass `--fork` (`--fork-session`) when the user wants to branch from a WorkBuddy session without modifying its original `.jsonl` transcript.
   - For multi-line or complex prompts, write the prompt to a temporary file and pass `--prompt-file <file>` (or pipe via stdin with `-`).
   - Note that CLI-appended turns write to the `.jsonl` file on disk; WorkBuddy Desktop UI will not live-stream them and may require switching sessions or refreshing to display new turns.

## Standard Commands

Let `SCRIPT` be the path to `scripts/workbuddy_bridge.py` inside this skill directory.
On Windows, if `python3` points to the Microsoft Store stub, invoke the script with `python`, `uv run python`, or WorkBuddy's bundled Python (`%USERPROFILE%\.workbuddy\binaries\python\versions\<ver>\python.exe`).

### 0. Check Bridge Health & CLI/Auth Readiness

```bash
python3 "$SCRIPT" doctor
```

### 1. List Recent Sessions

```bash
python3 "$SCRIPT" list --limit 15
python3 "$SCRIPT" list --cwd my-repo --limit 10
python3 "$SCRIPT" list --space my-space
python3 "$SCRIPT" list --query "auth"
```

### 2. Search Across Session Messages

```bash
python3 "$SCRIPT" search "keyword" --days 30 --limit 10
python3 "$SCRIPT" search "deploy" --cwd my-repo
```

### 3. Read a Specific Session

```bash
# Read the latest session (or latest in a given project)
python3 "$SCRIPT" read --last --cwd my-repo --last-turns 10

# Read by session UUID, UUID prefix, or title substring
python3 "$SCRIPT" read <SESSION_ID_OR_PREFIX> --last-turns 12 --final-only

# Deep read with tool calls / reasoning and pagination
python3 "$SCRIPT" read <SESSION_ID> --include-tools --offset 0 --limit 30 --max-chars 8000
```

### 4. Resume / Send a Message to an Existing Session

```bash
# Dry-run first to verify target, cwd, CLI binary, and flags
python3 "$SCRIPT" send <SESSION_ID> "总结你当前这轮改动和未完成项" --dry-run

# Read-only follow-up question (default --mode read-only)
python3 "$SCRIPT" send <SESSION_ID> "总结你当前这轮改动和未完成项"

# Branch without modifying the original WorkBuddy session transcript
python3 "$SCRIPT" send <SESSION_ID> "基于刚才方案给一个备选设计" --fork

# Allow edits in the session workspace (only when explicitly requested)
python3 "$SCRIPT" send <SESSION_ID> "按计划修复单测并验证" --mode edit
```

### 5. Start a New Non-Interactive Session

```bash
python3 "$SCRIPT" start "检查当前仓库的构建配置并给出风险清单" -C /path/to/repo --mode read-only
```

## Troubleshooting

- **`Authentication required. Please use /login command to sign in to your account`**:
  - Either export `CODEBUDDY_API_KEY` (and `CODEBUDDY_INTERNET_ENVIRONMENT=internal` for CN edition), or install `@tencent-ai/codebuddy-code` and run `python3 "$SCRIPT" login` to sign in via QR/browser.
- **`Refusing to send: session ... has status='working'`**:
  - Wait until the session completes in WorkBuddy Desktop before calling `send`, or use `--fork` to branch off a copy instead.
- **Ambiguous target**: Run `list --query <term>` first and pass the exact UUID or unique UUID prefix.
