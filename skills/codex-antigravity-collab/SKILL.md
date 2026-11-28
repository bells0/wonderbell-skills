---
name: codex-antigravity-collab
description: >-
  Orchestrate collaborative software development between Antigravity and OpenAI
  Codex using codex-bridge and antigravity-agent-bridge. Use when handing off
  or taking over an in-progress task between the two agents, running joint
  architecture or API contract reviews against real repository artifacts, or
  enforcing a build -> independent read-only review -> fix -> re-review closure
  loop before delivering work to the user.
---

# Codex + Antigravity Collaborative Development

Structured orchestration playbook for two-agent development between Antigravity and Codex. This skill owns **workflow, role boundaries, review closure, and safety rules**; delegate transport commands to the underlying bridge skills:

- **Antigravity -> Codex (primary cross-platform path)**: use `codex-bridge` (`list`/`search`/`read`/`start`/`send`, `--prompt-file`, `--name`, `--sandbox read-only`).
- **Codex -> Antigravity**: use `antigravity-agent-bridge` (`conversations`/`read --limit`/`new`/`send`/`wait` with `--project`, `--title`, `--message-file`) on supported macOS hosts. On Windows, `antigravity-agent-bridge` lacks a verified Windows-safe discovery/dispatch path (e.g., `os.kill(pid, 0)` and `.bat` entry point), so use manual Codex-to-Antigravity handoff until a Windows-verified bridge path is available. Note also that `antigravity-agent-bridge` exposes no `--sandbox read-only` CLI flag; read-only review on that route is a prompt-level constraint unless independently enforced by the environment.

Reusable prompt templates live in [references/handoff-and-review-templates.md](./references/handoff-and-review-templates.md).

## Non-Negotiable Guardrails

1. **Single-writer per worktree/file set**: Only one agent edits a given worktree or overlapping file set at a time. The reviewing agent runs read-only (`--sandbox read-only` when dispatching to Codex via `codex-bridge`, and explicit read-only instructions when dispatching to Antigravity) unless the user explicitly authorizes write handoff.
2. **Reuse existing worktrees**: When taking over or reviewing a task that already uses an isolated worktree (e.g., `.worktrees/<task>`), keep working in that worktree and branch. Never create nested worktrees or silently move work to external temporary directories.
3. **Client-visible, worktree-accurate, lock-safe dispatch**:
   - When Antigravity calls Codex on a registered project root, use `codex-bridge` defaults (`--via app-server`, auto-mapped project root) so threads stay visible in Codex Desktop.
   - When the assignment targets an isolated `.worktrees/<task>` (or unregistered subdirectory), start the thread with `-C "<worktree>" --exact-cwd` so Codex reviews or edits the worktree rather than the parent checkout.
   - Never send to or `--force` a `[LOCKED]` or `[RUNNING]` Codex session. Open a dedicated collaboration/review thread with a clear `--name` instead.
4. **File-based prompts and real Python interpreter**:
   - Write multi-line handoff or review packets to a temporary UTF-8 file and pass `--prompt-file <file>` (`codex-bridge`) or `--message-file <file>` (`antigravity-agent-bridge`) to avoid shell quoting corruption.
   - On Windows, avoid the Microsoft Store `python`/`python3` stub; invoke bridge scripts via `uv run python` or a project `.venv` Python.
5. **Independent judgment (no leading the reviewer)**: Provide raw artifacts, real sample files, diffs, constraints, and open questions. Do not tell the reviewer which conclusion you want approved.
6. **No authority escalation**: Neither agent may perform unapproved `git push`, PR creation, branch merge, production config/database changes, or external messages. Pass all user constraints verbatim in every dispatch packet.

## Workflow 1: Task Handoff & Context Takeover

Use when continuing work that started in the other agent.

1. **Progressive context read**:
   - **From Codex (`codex-bridge`)**: locate the source session (`list`/`search`), read recent turns first (`read ... --last-turns 10` or `--final-only`), and pull tool logs only if gaps remain.
   - **From Antigravity (`antigravity-agent-bridge`, macOS-verified)**: list targets (`conversations --project "<name>"`), read recent replies (`read CONVERSATION_ID --project "<name>" --limit 20`), or request a handoff summary from the user on Windows.
2. **Ground in real repository state**: Inspect `git status`, active branch, existing `.worktrees/`, untracked output folders that must be preserved, and referenced docs/samples. Treat actual files as the source of truth if they differ from earlier chat summaries.
3. **Confirm scope and boundaries**: Summarize inherited state, preserved artifacts, remaining deliverables, and explicit non-goals before making edits. Leave the source agent's `[LOCKED]` thread untouched.

## Workflow 2: Design & API Contract Joint Review

Use before coding when an architecture choice, schema, or API contract has non-trivial edge cases or real data samples to satisfy.

1. **Draft with real fixtures**: The lead agent drafts the concrete spec/contract and collects exact repository paths to real sample files, schemas, or existing parsers.
2. **Dispatch read-only review packet**: Build the prompt using the **Spec / Contract Review** template in [references/handoff-and-review-templates.md](./references/handoff-and-review-templates.md).
   - **Codex reviewer (`codex-bridge`)**: start a named read-only thread (`start --prompt-file <file> -C "<repo-or-worktree>" [--exact-cwd] --name "<topic> 契约评审" --sandbox read-only`).
   - **Antigravity reviewer (`antigravity-agent-bridge`, macOS-verified)**: dispatch via `new --project "<name>" --title "<topic>: review" --message-file <file> --wait 40` and collect with `wait ... --after-step <cursor>` (enforcing read-only via prompt constraint; use manual handoff on Windows).
3. **Require evidence-backed verdicts**: Ask the peer agent to inspect the real repository samples directly, challenge assumptions, flag fixture/field inconsistencies, and return numbered design rulings.
4. **Reconcile and lock**: Evaluate every finding against user requirements and actual files. Present the converged design and key trade-offs to the user; lock the contract only after user confirmation.

## Workflow 3: Build -> Independent Review -> Fix -> Re-Review Closure

Use when implementing features or fixes that must pass an independent peer review before delivery.

1. **Implement and self-verify**: Complete code, doc, and module README updates in the designated worktree. Run real local checks (unit/integration tests, type check, build, and safe smoke checks when local test credentials exist).
2. **Dispatch code review packet**: Use the **Implementation Review** template in [references/handoff-and-review-templates.md](./references/handoff-and-review-templates.md) with worktree path, branch, changed-file/diff scope, verification commands and outputs, and constraints. Send to a dedicated read-only peer thread (`codex-bridge` with `--sandbox read-only` and `--exact-cwd` when reviewing a worktree; or `antigravity-agent-bridge` on supported hosts / manual handoff on Windows).
3. **Triage findings by severity**:
   - **Blocking / Important**: Fix in code/docs, re-run affected checks, and prepare a concise delta summary.
   - **Minor / Out-of-scope**: Apply if cheap and clearly beneficial; otherwise record why it was deferred.
4. **Close the loop**: Send the delta summary and updated check outputs back to the same review thread (confirming it is unlocked via `codex-bridge` `send`, or `antigravity-agent-bridge` `send` + `wait`) for final sign-off. Sign-off requires zero unresolved **Blocking** or **Important** findings.
5. **Bounded escalation (max 2 review rounds)**: If substantive disagreement or any unresolved **Blocking**/**Important** finding remains after 2 rounds, stop looping and present both positions and outstanding findings with concrete file/test evidence to the user for a decision.
6. **Integrated user delivery**: Report the final outcome, exact verification evidence, key review decisions adopted or declined, and remaining risks. Do not dump raw inter-agent transcripts.

## Completion Checklist

- [ ] Active worktree/branch preserved with zero nested worktrees or unintended file loss.
- [ ] No `[LOCKED]`/`[RUNNING]` peer session was forcibly written.
- [ ] Verification commands ran on real code/artifacts and passed (or missing local credentials were explicitly reported without touching production).
- [ ] Peer review reached explicit `PASS` sign-off with zero unresolved **Blocking** or **Important** issues (or unresolved findings/trade-offs were escalated clearly to the user).
- [ ] `git status` / `git log` confirm the expected local branch, commits, and working-tree state, and no unauthorized push, PR, merge, or production change was executed.
