# Handoff & Review Packet Templates

Write the filled template to a temporary UTF-8 file and pass it via `--prompt-file <file>` (`codex-bridge`, or stdin) or `--message-file <file>` (`antigravity-agent-bridge`) instead of quoting multi-line text on the command line.

## 1. Spec / API Contract Joint Review Packet (Codex: `--sandbox read-only`; Antigravity: read-only by prompt)

```markdown
You are acting as an independent senior architect and contract reviewer collaborating with the lead agent. Do NOT edit files.

### Objective
Review and stress-test the proposed design / API contract for: <feature or endpoint>.

### Hard Constraints (User-Confirmed)
- <constraint 1>
- <constraint 2>
- Out of scope: <explicit non-goals>

### Repository Artifacts & Real Samples to Inspect
- Draft spec / contract: `<absolute or repo-relative path>`
- Real sample inputs / parsed outputs: `<paths>`
- Related existing code / docs: `<paths>`

### Open Decisions & Risk Areas
1. <question 1>
2. <question 2>

### Required Output Format
1. **Direct Verdict**: Approve as-is / Approve with specific changes / Redesign needed.
2. **Sample & Ground-Truth Discrepancies**: Any mismatch between the draft and actual repository samples/code (cite exact file paths).
3. **Numbered Design Rulings**: Concrete recommendations with rationale for each open decision and edge case.
4. **Minimal Example Check**: Verify that all variants map cleanly to the unified structure without cross-file fixture mixing.
```

## 2. Implementation & Diff Review Packet (Codex: `--sandbox read-only`; Antigravity: read-only by prompt)

```markdown
You are acting as an independent code reviewer. Inspect the actual files and git diff in the workspace; do NOT modify files.

### Task & Scope
- Goal: <concise summary of what was implemented>
- Worktree / Repo Path: `<path>`
- Branch / Base Commit: `<branch>` (base `<sha>`)
- Changed Areas: <backend / frontend / migrations / tests / docs>

### Verification Already Run
- `<command 1>` -> <pass/fail + key counts>
- `<command 2>` -> <pass/fail + key counts>
- Not run / skipped (and why): <e.g., no local test credentials; production untouched>

### Hard Constraints & Review Focus
- Must preserve: <untracked dirs, backward compatibility, existing worktree>
- Must NOT do: <no push/PR/merge/prod changes>
- Focus areas: <correctness, edge cases, contract drift, doc/README sync, regressions>

### Required Output Format
Return findings grouped by severity (`Blocking`, `Important`, `Minor`). For each finding include:
- **Location**: file path + line/symbol
- **Evidence & Impact**: what is wrong and why it matters
- **Concrete Fix**: minimal recommended change

End with an explicit verdict: `PASS` (zero blocking/substantive issues) or `CHANGES_REQUESTED`.
```

## 3. Re-Review Delta Packet (Codex: `--sandbox read-only`, reuse review thread; Antigravity: reuse conversation)

```markdown
Follow-up re-review for the previous `CHANGES_REQUESTED` findings. Do NOT edit files.

### Fixes Applied
1. [Finding #1] <what changed + file path>
2. [Finding #2] <what changed + file path>
3. [Deferred / Declined, if any] <reason + evidence>

### Updated Verification Results
- `<command>` -> <output summary>

Please verify each resolved finding against the current workspace files/diff and confirm whether the verdict is now `PASS` (zero unresolved `Blocking` or `Important` findings) or `CHANGES_REQUESTED` with any remaining `Blocking` or `Important` issues.
```
