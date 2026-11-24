# Antigravity Agent Bridge: scope and verification

## Request and placement

The user requested a durable Skill for the proven CLI interaction between Codex and Antigravity agents, with the implementation committed and pushed to an appropriate project. The intended user flow is: name an Antigravity project or conversation, dispatch a bounded assignment, and collect the response without desktop clicking.

This belongs in `wonderbell-skills`: it is an original reusable capability and local integration helper. `agent-teamworks` remains responsible for durable team formation and role continuity. This change adds no scheduler, background daemon, persistent team framework, or permission policy to that plugin.

## Implementation and acceptance contract

One deliverable comprises the Skill, Python helper, interface reference, enabled custom catalog entry, and README discovery link. The helper consumes the already installed application's CLI and loopback interface. No vendor source or executable is redistributed, and no extra Python package is needed at runtime.

The implementation sequence was to verify the installed interface, implement project/conversation discovery and dispatch, then verify the actual new-conversation → message → new-response flow before installation and Git delivery. The owning agent handles branch, commit, push, and PR; review and merge remain with the repository owner or an authorized reviewer.

Acceptance requires:

1. Discover a running local application without persisting or printing its token.
2. Resolve the named project's ID and folders, and list its conversations.
3. Create a conversation in that project and verify returned project/workspace metadata.
4. Send a UTF-8 task through `agentapi`, then read a fresh matching reply from that conversation.
5. Reject a send when the conversation belongs to another project, without adding any trajectory step.
6. Return `received_reply: false` for a wait after the current cursor, even when the conversation is idle and has earlier replies.
7. Enable installation through the existing catalog and pass the relevant repository checks.

The public integration is original MIT-licensed repository code. Interface details were observed from the installed Antigravity App 2.34.0 and its CLI help. The separate official `agy` CLI is documented in the linked [interface reference](../skills/antigravity-agent-bridge/references/local-interface.md).

## Verification on 2026-11-25

Real application verification on macOS with Antigravity App 2.34.0 passed acceptance items 1–6. Creation returned the selected project's ID and local folders; the created conversation's parent was empty. A subsequent Chinese message delivered through stdin received its requested task-ID-bearing response. The wrong-project attempt was rejected and its before/after trajectory step count was unchanged. Waiting after the current cursor with a zero-second timeout returned no new replies rather than accepting historical text.

The live acceptance used the bundled helper, not a mocked service. Machine-specific conversation IDs, discovery records, prompts, and replies remain outside Git in the local Codex state directory.

Checks passed:

```bash
uv run --with pyyaml python /path/to/skill-creator/scripts/quick_validate.py \
  skills/antigravity-agent-bridge
bash scripts/test-install.sh
bash scripts/test-audit-local-skills.sh
bash scripts/test-check-skill-drift.sh
git diff --check
```

`PyYAML` is only needed by the external Skill validator; the helper uses Python's standard library. Syntax was also checked with Python's AST parser without generating cache files in the Skill.

For a repeatable live check, use an existing disposable test project and a prompt instructing the agent to reply with a fixed marker without using tools:

```bash
python3 "$BRIDGE" projects
python3 "$BRIDGE" new --project "$PROJECT_NAME" --title "Bridge smoke test" \
  --message-file /absolute/path/test-prompt.txt --wait 40
python3 "$BRIDGE" send "$CONVERSATION_ID" --project "$PROJECT_NAME" \
  --title "TASK-2" --message-file /absolute/path/follow-up.txt --wait 40
python3 "$BRIDGE" read "$CONVERSATION_ID" --project "$PROJECT_NAME"
python3 "$BRIDGE" wait "$CONVERSATION_ID" --project "$PROJECT_NAME" \
  --after-step "$NEXT_STEP" --timeout 0
```

Use the conversation ID and cursor actually returned by each command. A timeout after sending does not authorize sending the same task again. The owner remains responsible for accepting actual task artifacts; a transport reply alone is not completed work.

## Limits and rollback

Internal interfaces may change after an application upgrade. Multiple simultaneous local application instances, long-history pagination, custom profiles/model flags, and remote/cloud project creation were not exercised in the live acceptance. Remote/cloud creation is deliberately rejected when no verified local folder is available. An agent/system message is delivered as such, not as a user keystroke. Conversations can batch queued messages, so callers keep one active assignment per conversation and correlate task IDs themselves.

The bridge does not grant additional permissions or synchronize Codex and Antigravity histories. Long tasks are followed through repeated bounded waits on the same conversation; there is no unattended polling service.

To undo local discovery, remove only the `antigravity-agent-bridge` symlink from the local Skills directory. Revert the feature commit to remove the source/catalog registration. No changes to Antigravity installation, credentials, shell profiles, or service configuration are required.
