from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_image.py"
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class Handler(BaseHTTPRequestHandler):
    requests = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        type(self).requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "content_type": self.headers.get("Content-Type"),
                "body": body,
            }
        )
        payload = json.dumps(
            {"data": [{"b64_json": base64.b64encode(PNG).decode()}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):
        pass


class GenerateImageTests(unittest.TestCase):
    def setUp(self):
        Handler.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def env_file(self, root: Path) -> Path:
        path = root / ".env"
        path.write_text(
            "IMAGEGEN_API_KEY=test-secret\n"
            f"IMAGEGEN_BASE_URL=http://127.0.0.1:{self.server.server_port}/v1\n",
            encoding="utf-8",
        )
        return path

    def run_script(self, *arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_check_does_not_call_api_or_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = self.env_file(root)
            prompt = root / "prompt.txt"
            prompt.write_text("A blue ceramic cup", encoding="utf-8")
            result = self.run_script(
                "--check",
                "--env-file",
                str(env),
                "--prompt-file",
                str(prompt),
                cwd=root,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('"action": "check-only"', result.stdout)
            self.assertEqual(Handler.requests, [])
            self.assertFalse((root / "generated-images").exists())

    def test_generation_saves_trace_without_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = self.env_file(root)
            output = root / "out"
            result = self.run_script(
                "--execute",
                "--env-file",
                str(env),
                "--prompt",
                "A paper lantern",
                "--name",
                "lantern",
                "--output-dir",
                str(output),
                cwd=root,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            run_dir = next((output / "lantern").iterdir())
            self.assertTrue((run_dir / "01.png").is_file())
            self.assertEqual((run_dir / "01.png").read_bytes(), PNG)
            combined = (
                (run_dir / "request.json").read_text()
                + (run_dir / "run.json").read_text()
            )
            self.assertNotIn("test-secret", combined)
            response_record = (run_dir / "response.json").read_text()
            self.assertIn("<omitted after local image save>", response_record)
            self.assertNotIn(base64.b64encode(PNG).decode(), response_record)
            self.assertEqual(Handler.requests[0]["authorization"], "Bearer test-secret")
            self.assertEqual(Handler.requests[0]["path"], "/v1/images/generations")

    def test_reference_uses_edits_multipart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = self.env_file(root)
            reference = root / "source.png"
            reference.write_bytes(PNG)
            result = self.run_script(
                "--execute",
                "--env-file",
                str(env),
                "--prompt",
                "Keep the object blue",
                "--reference",
                str(reference),
                "--output-dir",
                str(root / "out"),
                cwd=root,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            request = Handler.requests[0]
            self.assertEqual(request["path"], "/v1/images/edits")
            self.assertTrue(request["content_type"].startswith("multipart/form-data;"))
            self.assertIn(b'name="image[]"; filename="source.png"', request["body"])
            self.assertIn(PNG, request["body"])


if __name__ == "__main__":
    unittest.main()
