from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "configure.py"
GENERATOR = Path(__file__).resolve().parents[1] / "scripts" / "generate_image.py"


class ConfigureTests(unittest.TestCase):
    def run_script(
        self, *arguments: str, cwd: Path, extra_env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update(extra_env)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            cwd=cwd,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_ark_preset_writes_private_env_without_echoing_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / ".env"
            target.write_text("UNRELATED=value\nIMAGEGEN_TIMEOUT_SECONDS=240\n", encoding="utf-8")
            result = self.run_script(
                "ark",
                "--env-file",
                str(target),
                "--api-key-env",
                "TEST_ARK_KEY",
                cwd=root,
                extra_env={"TEST_ARK_KEY": "private-test-key"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = target.read_text(encoding="utf-8")
            self.assertIn("UNRELATED=value", content)
            self.assertIn("IMAGEGEN_PROVIDER=ark", content)
            self.assertIn("IMAGEGEN_API_KEY=private-test-key", content)
            self.assertIn(
                "IMAGEGEN_BASE_URL=https://ark.cn-beijing.volces.com/api/v3", content
            )
            self.assertIn("IMAGEGEN_MODEL=doubao-seedream-5-0-pro-260628", content)
            self.assertIn("IMAGEGEN_TIMEOUT_SECONDS=240", content)
            self.assertNotIn("private-test-key", result.stdout)
            self.assertNotIn("private-test-key", result.stderr)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            check = subprocess.run(
                [
                    sys.executable,
                    str(GENERATOR),
                    "--check",
                    "--env-file",
                    str(target),
                    "--prompt",
                    "A ceramic cup",
                ],
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(check.returncode, 0, check.stderr)
            self.assertIn('"provider": "ark"', check.stdout)

    def test_keep_existing_key_does_not_duplicate_assignments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / ".env"
            target.write_text(
                "IMAGEGEN_API_KEY=existing-key\n"
                "IMAGEGEN_PROVIDER=openai-compatible\n"
                "IMAGEGEN_PROVIDER=stale-duplicate\n",
                encoding="utf-8",
            )
            result = self.run_script(
                "ark",
                "--env-file",
                str(target),
                "--keep-existing-key",
                cwd=root,
                extra_env={},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            content = target.read_text(encoding="utf-8")
            self.assertEqual(content.count("IMAGEGEN_PROVIDER="), 1)
            self.assertEqual(content.count("IMAGEGEN_API_KEY="), 1)
            self.assertIn("IMAGEGEN_API_KEY=existing-key", content)
            self.assertNotIn("existing-key", result.stdout)


if __name__ == "__main__":
    unittest.main()
