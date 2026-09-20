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
LAUNCHER = Path(__file__).resolve().parents[1] / "scripts" / "setup-seedream.command"


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

    def test_default_user_config_is_found_automatically(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_home = root / "config"
            environment = os.environ.copy()
            environment.update(
                {
                    "XDG_CONFIG_HOME": str(config_home),
                    "TEST_ARK_KEY": "private-test-key",
                }
            )
            configured = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "ark",
                    "--api-key-env",
                    "TEST_ARK_KEY",
                ],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(configured.returncode, 0, configured.stderr)
            target = config_home / "wonderbell-imagegen" / ".env"
            self.assertTrue(target.is_file())
            checked = subprocess.run(
                [sys.executable, str(GENERATOR), "--check", "--prompt", "A teacup"],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertIn('"provider": "ark"', checked.stdout)

    def test_double_click_launcher_only_needs_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / ".env"
            environment = os.environ.copy()
            environment["TEST_ARK_KEY"] = "private-test-key"
            result = subprocess.run(
                [
                    "/bin/zsh",
                    str(LAUNCHER),
                    "--api-key-env",
                    "TEST_ARK_KEY",
                    "--env-file",
                    str(target),
                ],
                cwd=root,
                env=environment,
                input="\n",
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("配置完成", result.stdout)
            self.assertNotIn("private-test-key", result.stdout + result.stderr)
            self.assertTrue(target.is_file())


if __name__ == "__main__":
    unittest.main()
