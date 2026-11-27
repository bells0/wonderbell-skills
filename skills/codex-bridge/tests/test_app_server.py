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


if __name__ == "__main__":
    unittest.main()
