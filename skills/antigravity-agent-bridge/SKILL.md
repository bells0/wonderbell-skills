---
name: antigravity-agent-bridge
description: Coordinate with Antigravity agents through its installed local agentapi CLI and authenticated loopback service. Use to find a project or conversation, start an agent conversation, send a scoped task, and read or wait for its reply without desktop clicking.
---

# Antigravity Agent Bridge

Use the running Antigravity application's own `agentapi`, with the bundled Python helper supplying local discovery and compact reply reads. Python 3.10+ is sufficient; no extra packages, CLI installation, application restart, or desktop automation are needed.

## Find the target

Resolve `scripts/antigravity_bridge.py` relative to this Skill directory. In the examples, `$BRIDGE` means that absolute script path.

```bash
python3 "$BRIDGE" status
python3 "$BRIDGE" projects
python3 "$BRIDGE" conversations --project "project-name"
python3 "$BRIDGE" metadata CONVERSATION_ID --project "project-name"
python3 "$BRIDGE" read CONVERSATION_ID --project "project-name" --limit 20
```

Use the user's named project and existing conversation when continuing work. Project names must match exactly; use a project ID if names repeat. Confirm the returned project ID, folders, and conversation title before assigning work. Do not confuse the currently focused desktop project with the requested project.

If no service is running, ask the user to open Antigravity. If multiple local instances are active, select `--daemon-file /absolute/path/to/hub_PORT.json` explicitly rather than guessing. This flag precedes the subcommand. Do not print or copy the discovery file: it contains a local authentication token.

## Dispatch and collect

Prefer UTF-8 files or stdin for task text; do not interpolate tasks into shell commands.

```bash
python3 "$BRIDGE" send CONVERSATION_ID --project "project-name" \
  --title "TASK-123: review" --message-file /absolute/path/task.txt --wait 40

# New conversation in an existing project; only when the task calls for one.
python3 "$BRIDGE" new --project "project-name" --title "TASK-124: research" \
  --message-file /absolute/path/task.txt --wait 40
```

`send` returns the conversation ID and a `start_step` cursor. `new` also verifies the resulting project and workspace metadata. `--wait` is optional and capped at 60 seconds so the caller can keep communicating with the user. Continue collecting from the returned cursor:

```bash
python3 "$BRIDGE" wait CONVERSATION_ID --project "project-name" \
  --after-step START_STEP --timeout 40
```

Read `delivery`, `received_reply`, `timed_out`, `status`, and `replies` separately. Delivery acceptance is not a reply, and a reply is not task acceptance. `wait` requires a new response after the cursor and an idle run; old replies do not satisfy it. When waiting times out, keep the same conversation and cursor. If sending times out, the delivery outcome is unknown: inspect that conversation before retrying. Never automatically resend a mutating request.

## Coordinate several agents

- Keep one active assignment per conversation. Separate independent workstreams into their own conversations; responses are not individually linked to queued messages by this transport.
- Include a task ID, source/coordinator, objective, owned files or responsibilities, constraints, acceptance evidence, and where to return the result. Ask the recipient to include the task ID in its reply.
- For shared repositories, tell each worker it is not alone, to preserve others' changes, and to stay within its ownership. Reuse an existing role's conversation when available.
- Collect progress and evidence, resolve dependencies, and summarize the combined result in the coordinating chat. Check artifacts or real behavior before declaring an assignment complete.
- Delegate only work authorized by the user. A transport Skill does not authorize messages to people, publication, spending, merge, production changes, or wider access. Pass through applicable project instructions and user restrictions. In particular, do not assign or indirectly perform any WeChat operation when the user forbids it.

## Compatibility and boundaries

Verified against Antigravity App 2.34.0 on macOS. The helper calls internal application interfaces, which may change after upgrades. An incompatible response is a reason to inspect the current installed `agentapi --help` and owning interface, not to switch to an unrelated agent or silently fall back to desktop control.

See [references/local-interface.md](references/local-interface.md) for discovery, interface shapes, and the distinction from the separately installed official `agy` CLI. Runtime tokens, real conversation IDs, prompts, replies, and daemon files belong outside the public repository.
