# Local Antigravity interface

Observed with Antigravity App 2.34.0 on macOS. These are internal interfaces of the installed application, not a promised public API. This package contains original integration instructions and a client; it redistributes no Antigravity binary, application source, credentials, or user data.

## Installed command and discovery

- Entry point: `~/.gemini/antigravity/bin/agentapi`.
- On the verified installation it launches the app's `Contents/Resources/bin/language_server` with the `agentapi` subcommand.
- `agentapi --help` lists `get-conversation-metadata`, `new-conversation`, and `send-message`.
- A running instance publishes `~/.gemini/antigravity/daemon/hub_*.json` containing `pid`, `httpPort`, `httpsPort`, `lsVersion`, and `csrfToken`.
- Despite the filename's number, use the `httpPort` field for the local HTTP client. Use `http://127.0.0.1:<httpPort>`; the other port uses TLS.
- Supply `ANTIGRAVITY_LS_ADDRESS`, `ANTIGRAVITY_CSRF_TOKEN`, and `ANTIGRAVITY_LS_VERSION` privately in the child environment. New conversations also use `ANTIGRAVITY_PROJECT_ID` and the selected project's local working directory.
- A stale daemon file is not proof of a running instance. The helper checks its PID and makes an authenticated read. Multiple live records require an explicit choice.

Do not save tokens in a shell profile, print discovery contents, expose the endpoint on the network, or disable TLS verification. The helper uses the existing loopback HTTP endpoint and does not follow redirects or use a proxy.

## Compact read endpoints

JSON POST requests use `/exa.language_server_pb.LanguageServerService/<Method>` with `Content-Type: application/json`, `Connect-Protocol-Version: 1`, and `x-codeium-csrf-token`. Read methods used by the helper:

| Method | Request | Useful response |
| --- | --- | --- |
| `ListProjects` | `{}` | `projectIds` |
| `ReadProjects` | `{"ids":["PROJECT_ID"]}` | `projects` with `id`, `name`, and `projectResources.resources` |
| `GetAllCascadeTrajectories` | `{}` | `trajectorySummaries` keyed by conversation ID; `trajectoryMetadata.projectId` scopes them |
| `GetCascadeTrajectory` | `{"cascadeId":"CONVERSATION_ID"}` | `status`, `numTotalSteps`, and `trajectory.steps` |
| `GetCascadeTrajectorySteps` | `{"cascadeId":"CONVERSATION_ID","stepOffset":100}` | Additional `steps` when the first response is truncated |

Project resources observed were `folderUri` and `gitFolder.folderUri`. The helper creates conversations only for projects with a verified local folder. Remote/cloud project creation is outside this implementation.

The metadata CLI returns `response.conversationMetadata.metadata` with `projectId`, `workspaceUris`, and `parentConversationId`. Creation returns `response.newConversation.conversationId`. The installed CLI help warns that an unavailable model ID can fall back to its flash tier; if a model is an acceptance requirement, verify the actual model separately rather than trusting the requested flag.

`send-message` inserts an agent/system message and can wake an idle agent. It is not a simulated user keystroke. Its immediate JSON receipt confirms delivery acceptance, not successful work. Assistant text is read from `plannerResponse.response`; `thinkingSignature`, full configurations, and raw tool payloads are deliberately omitted.

A cursor is the number of trajectory steps before dispatch. It prevents old answers from satisfying a wait, but does not correlate independently queued tasks to replies. Use one active assignment per conversation and task IDs in the task/result text. An idle status alone never proves success.

## Separate official CLI

The separately distributed official [`agy` CLI](https://antigravity.google/docs/getting-started?tab=cli) supports [headless prompts and JSON streaming](https://antigravity.google/docs/cli/headless/), including `agy -p`, `--conversation`, and `--continue`.

This Skill uses the already running desktop application's `agentapi` to preserve its actual project/conversation routing. It does not install `agy`, change sign-in, or assume that a separate CLI's history maps to a desktop conversation. If choosing `agy` instead, verify its installed version, workspace, history, and authentication separately.
