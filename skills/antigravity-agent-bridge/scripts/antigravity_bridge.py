#!/usr/bin/env python3
"""Small, dependency-free bridge to a running local Antigravity App."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class BridgeError(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def discover(explicit=None):
    candidates = []
    paths = [Path(explicit)] if explicit else sorted(
        (Path.home() / ".gemini/antigravity/daemon").glob("hub_*.json")
    )
    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            pid = int(record["pid"])
            if pid <= 0:
                raise ValueError("invalid PID")
            os.kill(pid, 0)
            port = int(record["httpPort"])
            token = record["csrfToken"]
            if not 0 < port < 65536 or not isinstance(token, str) or not token:
                raise ValueError("invalid port or token")
            candidates.append((path, record))
        except (OSError, ValueError, KeyError, TypeError):
            if explicit:
                raise BridgeError("The selected daemon file is invalid or its process is not running.")
    if not candidates:
        raise BridgeError("No running Antigravity App found. Open the app first.")
    if len(candidates) != 1:
        raise BridgeError("Multiple instances found; choose --daemon-file explicitly: "
                          + ", ".join(str(item[0]) for item in candidates))
    return candidates[0]


class Bridge:
    def __init__(self, args):
        self.daemon_file, self.record = discover(args.daemon_file)
        self.token = self.record["csrfToken"]
        self.base = "http://127.0.0.1:" + str(self.record["httpPort"])
        self.binary = Path(args.agentapi).expanduser() if args.agentapi else (
            Path.home() / ".gemini/antigravity/bin/agentapi"
        )
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def rpc(self, method, payload):
        req = urllib.request.Request(
            self.base + "/exa.language_server_pb.LanguageServerService/" + method,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Connect-Protocol-Version": "1",
                     "x-codeium-csrf-token": self.token},
        )
        try:
            with self.opener.open(req, timeout=10) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise BridgeError(f"{method}: HTTP {exc.code}; check app/interface compatibility.") from None
        except (OSError, ValueError) as exc:
            raise BridgeError(f"{method}: {exc}") from None

    def cli(self, command, *values, project_id=None, cwd=None):
        if not self.binary.is_file():
            raise BridgeError("Installed agentapi not found; supply --agentapi or inspect the app installation.")
        env = os.environ.copy()
        # Do not inherit another agent's parent/trajectory identity.
        for name in ("ANTIGRAVITY_CONVERSATION_ID", "ANTIGRAVITY_TRAJECTORY_ID", "ANTIGRAVITY_PROJECT_ID"):
            env.pop(name, None)
        env.update({"ANTIGRAVITY_LS_ADDRESS": self.base, "ANTIGRAVITY_CSRF_TOKEN": self.token,
                    "ANTIGRAVITY_LS_VERSION": str(self.record.get("lsVersion", ""))})
        if project_id:
            env["ANTIGRAVITY_PROJECT_ID"] = project_id
        try:
            result = subprocess.run([str(self.binary), command, *values], env=env,
                                    cwd=cwd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            raise BridgeError(f"{command} timed out; delivery may have occurred. Inspect the target "
                              "conversation/project before retrying; do not resend automatically.") from None
        if result.returncode:
            raise BridgeError(result.stderr.strip() or result.stdout.strip() or f"{command} failed")
        try:
            data = json.loads(result.stdout)
            if not isinstance(data, dict):
                raise ValueError("expected object")
            if data.get("error"):
                raise BridgeError(str(data["error"]))
            return data["response"]
        except (ValueError, KeyError, TypeError):
            raise BridgeError(f"Unexpected {command} response; inspect the installed agentapi interface.") from None

    def projects(self):
        ids = self.rpc("ListProjects", {}).get("projectIds", [])
        response = self.rpc("ReadProjects", {"ids": ids}) if ids else {"projects": []}
        if response.get("errorMessages"):
            raise BridgeError("Some projects could not be read; inspect the app before selecting a target.")
        return [{"id": p["id"], "name": p.get("name", ""), "folders": folder_uris(p)}
                for p in response.get("projects", [])]

    def project(self, selector):
        projects = self.projects()
        matches = [p for p in projects if p["id"] == selector]
        matches = matches or [p for p in projects if p["name"] == selector]
        if len(matches) != 1:
            raise BridgeError("Project missing or ambiguous; list projects and use an exact ID.")
        return matches[0]

    def metadata(self, cid, project=None):
        response = self.cli("get-conversation-metadata", cid)
        try:
            metadata = response["conversationMetadata"]["metadata"]
        except (KeyError, TypeError):
            raise BridgeError("Unexpected conversation metadata; cannot verify the target.") from None
        if project and metadata.get("projectId") != project["id"]:
            raise BridgeError("Conversation belongs to another project; no message was sent.")
        return {"conversation_id": cid, "project_id": metadata.get("projectId", ""),
                "workspace_uris": metadata.get("workspaceUris", []),
                "parent_conversation_id": metadata.get("parentConversationId", "")}

    def trajectory(self, cid):
        result = self.rpc("GetCascadeTrajectory", {"cascadeId": cid})
        if not result.get("trajectory"):
            raise BridgeError("Conversation trajectory not found.")
        steps = list(result["trajectory"].get("steps", []))
        total = int(result.get("numTotalSteps", len(steps)))
        while len(steps) < total:
            batch = self.rpc("GetCascadeTrajectorySteps", {"cascadeId": cid, "stepOffset": len(steps)})
            more = batch.get("steps", [])
            if not more:
                raise BridgeError("Incomplete trajectory page; do not interpret this as completion.")
            steps.extend(more)
        return result.get("status", ""), steps

    def read(self, cid, after=0, limit=20):
        status, steps = self.trajectory(cid)
        selected = list(enumerate(steps))[after:]
        rows = [compact_step(index, step) for index, step in selected[-limit:]]
        return {"conversation_id": cid, "status": status, "next_step": len(steps),
                "after_step": after, "steps": rows,
                "replies": [row for row in rows if row["type"] == "CORTEX_STEP_TYPE_PLANNER_RESPONSE"
                            and row.get("text")]}

    def wait(self, cid, after, seconds):
        deadline = time.monotonic() + seconds
        while True:
            result = self.read(cid, after, 100)
            complete = bool(result["replies"]) and result["status"] == "CASCADE_RUN_STATUS_IDLE"
            result.update(received_reply=complete, timed_out=False)
            if complete:
                return result
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                result["timed_out"] = True
                return result
            time.sleep(min(2, remaining))


def folder_uris(project):
    uris = []
    for resource in project.get("projectResources", {}).get("resources", []):
        uri = resource.get("folderUri") or resource.get("gitFolder", {}).get("folderUri")
        if uri:
            uris.append(uri)
    return uris


def compact_step(index, step):
    row = {"step": index, "type": step.get("type", ""), "status": step.get("status", "")}
    if "plannerResponse" in step:
        row["text"] = step["plannerResponse"].get("response", "")
    elif "userInput" in step:
        row["text"] = step["userInput"].get("userResponse", "")
    elif "systemMessage" in step:
        message = step["systemMessage"]
        row["text"] = message.get("agentMessage", {}).get("content") or message.get("message", "")
        row["message_id"] = message.get("agentMessage", {}).get("id", "")
    # Never emit raw metadata, thinking signatures, or whole tool payloads.
    return row


def message_text(args):
    if args.message_file:
        text = sys.stdin.read() if args.message_file == "-" else Path(args.message_file).read_text(encoding="utf-8")
    else:
        text = args.message
    if not text or not text.strip():
        raise BridgeError("Message must not be empty.")
    return text


def bounded_seconds(value):
    number = float(value)
    if not 0 <= number <= 60:
        raise argparse.ArgumentTypeError("Use 0–60 seconds; continue from the returned cursor for longer work.")
    return number


def nonnegative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("Must be nonnegative.")
    return number


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--daemon-file", help="Choose a local discovery file when multiple instances run")
    root.add_argument("--agentapi", help="Override the installed agentapi executable path")
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("projects")
    listing = sub.add_parser("conversations")
    listing.add_argument("--project", required=True)
    for name in ("metadata", "read", "wait", "send"):
        cmd = sub.add_parser(name)
        cmd.add_argument("conversation_id")
        cmd.add_argument("--project", required=True, help="Exact project name or ID; checked before sending")
        if name in ("read", "wait"):
            cmd.add_argument("--after-step", type=nonnegative, default=0, required=name == "wait")
        if name == "read":
            cmd.add_argument("--limit", type=int, default=20)
        if name == "wait":
            cmd.add_argument("--timeout", type=bounded_seconds, default=40)
    new = sub.add_parser("new")
    new.add_argument("--project", required=True)
    new.add_argument("--model", help="Only pin a model when requested; otherwise use agentapi defaults")
    new.add_argument("--profile", help="Optional installed Antigravity agent profile")
    for cmd in (sub.choices["send"], new):
        cmd.add_argument("--title", required=True)
        msg = cmd.add_mutually_exclusive_group(required=True)
        msg.add_argument("--message")
        msg.add_argument("--message-file", help="UTF-8 file, or - for stdin")
        cmd.add_argument("--wait", type=bounded_seconds, default=0)
    return root


def run(bridge, args):
    if args.command == "status":
        projects = bridge.projects()  # Verify that the recorded endpoint is reachable and authenticated.
        return {"version": bridge.record.get("lsVersion"), "daemon_file": str(bridge.daemon_file),
                "agentapi": str(bridge.binary), "agentapi_exists": bridge.binary.is_file(),
                "project_count": len(projects)}
    if args.command == "projects":
        return {"projects": bridge.projects()}
    project = bridge.project(args.project)
    if args.command == "conversations":
        summaries = bridge.rpc("GetAllCascadeTrajectories", {}).get("trajectorySummaries", {})
        conversations = []
        for cid, summary in summaries.items():
            if summary.get("trajectoryMetadata", {}).get("projectId") == project["id"]:
                conversations.append({"conversation_id": cid, "title": summary.get("summary", ""),
                                      "status": summary.get("status", ""),
                                      "modified_at": summary.get("lastModifiedTime", "")})
        return {"project": project, "conversations": sorted(conversations, key=lambda c: c["modified_at"], reverse=True)}
    if args.command == "new":
        folders = [urllib.parse.urlparse(uri) for uri in project["folders"]]
        local = [Path(urllib.parse.unquote(uri.path)) for uri in folders
                 if uri.scheme == "file" and uri.netloc in ("", "localhost")]
        if not local or not local[0].is_dir():
            raise BridgeError("New conversations require a verified local project folder; no conversation was started.")
        flags = ["--title=" + args.title]
        if args.model:
            flags.append("--model=" + args.model)
        if args.profile:
            flags.append("--profile=" + args.profile)
        result = bridge.cli("new-conversation", *flags, message_text(args), project_id=project["id"], cwd=local[0])
        cid = result.get("newConversation", {}).get("conversationId")
        if not cid:
            raise BridgeError("No conversation ID returned. Inspect the project before starting another conversation.")
        try:
            metadata = bridge.metadata(cid, project)
            if not set(project["folders"]).issubset(metadata["workspace_uris"]):
                raise BridgeError("Workspace folders differ from the selected project's folders.")
        except BridgeError as exc:
            raise BridgeError(f"Conversation {cid} was started, but its project could not be verified: {exc}") from None
        receipt = {**metadata, "delivery": "accepted", "start_step": 0}
    else:
        cid = args.conversation_id
        metadata = bridge.metadata(cid, project)
        if args.command == "metadata":
            return metadata
        if args.command == "read":
            if args.limit <= 0:
                raise BridgeError("--limit must be positive.")
            return bridge.read(cid, args.after_step, args.limit)
        if args.command == "wait":
            return bridge.wait(cid, args.after_step, args.timeout)
        _, before = bridge.trajectory(cid)
        bridge.cli("send-message", "--title=" + args.title, cid, message_text(args), project_id=project["id"])
        receipt = {**metadata, "delivery": "accepted", "start_step": len(before)}
    if args.wait:
        receipt["result"] = bridge.wait(cid, receipt["start_step"], args.wait)
    return receipt


def main():
    args = parser().parse_args()
    bridge = None
    try:
        bridge = Bridge(args)
        result = run(bridge, args)
        output = json.dumps(result, ensure_ascii=False, indent=2)
        print(output.replace(bridge.token, "[REDACTED]"))
        return 0
    except (BridgeError, OSError, ValueError, KeyError, TypeError) as exc:
        message = str(exc)
        if bridge:
            message = message.replace(bridge.token, "[REDACTED]")
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
