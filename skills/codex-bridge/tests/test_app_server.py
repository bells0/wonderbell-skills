import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import codex_bridge


def reply(request_id, **result):
    return {"id": request_id, "result": result}


def completed(thread, turn, status):
    return {
        "method": "turn/completed",
        "params": {"threadId": thread, "turn": {"id": turn, "status": status}},
    }


def message(thread, turn, text):
    return {
        "method": "item/completed",
        "params": {
            "threadId": thread,
            "turnId": turn,
            "item": {"type": "agentMessage", "phase": "final_answer", "text": text},
        },
    }


class AppServerTests(unittest.TestCase):
    def drive(self, events, name=None):
        events = [reply(1), reply(2, thread={"id": "main"}), *events]
        process = Mock(
            stdin=io.StringIO(),
            stdout=io.StringIO("".join(json.dumps(event) + "\n" for event in events)),
            stderr=io.StringIO(),
        )
        output = io.StringIO()
        with patch.object(codex_bridge.subprocess, "Popen", return_value=process), redirect_stdout(output):
            code = codex_bridge.run_codex_app_server("codex", "start", "hello", want_json=True, thread_name=name)
        return code, json.loads(output.getvalue())

    def test_interleaved_notifications_before_start_response(self):
        code, data = self.drive([
            completed("main", "previous", "completed"),
            message("main", "current", "wanted"),
            message("child", "current", "unrelated"),
            reply(3, turn={"id": "current"}),
            completed("main", "current", "interrupted"),
            reply(4),
        ])
        self.assertEqual(code, 1)
        self.assertEqual(data["last_message"], "wanted")
        self.assertIn("interrupted", " ".join(data["errors"]))

    def test_completion_before_start_response(self):
        code, data = self.drive([
            message("main", "current", "done"),
            completed("main", "current", "completed"),
            reply(3, turn={"id": "current"}),
            reply(4),
        ])
        self.assertEqual(code, 0)
        self.assertEqual(data["last_message"], "done")

    def test_requested_name_failure(self):
        code, data = self.drive([
            reply(3, turn={"id": "current"}),
            completed("main", "current", "completed"),
            {"id": 4, "error": {"code": -32000, "message": "name rejected"}},
            reply(5),
        ], name="display name")
        self.assertEqual(code, 1)
        self.assertIn("name rejected", " ".join(data["errors"]))

    def test_mapped_project_root_kept_for_turn_start(self):
        events = [
            reply(1),
            reply(2, thread={"id": "main"}),
            reply(3, turn={"id": "current"}),
            message("main", "current", "ok"),
            completed("main", "current", "completed"),
            reply(4),
        ]
        sent_lines = []

        class RecordingStdin(io.StringIO):
            def write(self, s):
                sent_lines.append(s)
                return super().write(s)

        process = Mock(
            stdin=RecordingStdin(),
            stdout=io.StringIO("".join(json.dumps(event) + "\n" for event in events)),
            stderr=io.StringIO(),
        )
        output = io.StringIO()
        args = codex_bridge.build_parser().parse_args([
            "start",
            "hello",
            "-C",
            r"D:\GitProjects\wonderbell-skills",
            "--json",
        ])
        with (
            patch.object(codex_bridge, "ensure_codex_binary", return_value="codex"),
            patch.object(codex_bridge, "resolve_default_model", return_value="gpt-test"),
            patch.object(
                codex_bridge,
                "resolve_client_project_cwd",
                return_value=(r"D:\GitProjects", r"D:\GitProjects\wonderbell-skills", {"id": "p1", "name": "GitProjects", "path": r"D:\GitProjects"}),
            ),
            patch.object(codex_bridge.subprocess, "Popen", return_value=process),
            redirect_stdout(output),
        ):
            code = codex_bridge.cmd_start(args)
        self.assertEqual(code, 0)
        sent = [json.loads(line) for line in "".join(sent_lines).splitlines() if line.strip()]
        by_method = {m["method"]: m.get("params") for m in sent if "method" in m}
        self.assertEqual(by_method["thread/start"]["cwd"], r"D:\GitProjects")
        self.assertEqual(by_method["turn/start"]["cwd"], r"D:\GitProjects")


if __name__ == "__main__":
    unittest.main()
