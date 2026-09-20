#!/usr/bin/env python3
"""Safely configure a local .env for the image generation skill."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
import tempfile
import urllib.parse
from pathlib import Path
from typing import Dict, Iterable, Optional


ASSIGNMENT = re.compile(r"^(?P<prefix>\s*(?:export\s+)?)(?P<name>[A-Za-z_][A-Za-z0-9_]*)=")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PRESETS = {
    "ark": {
        "provider": "ark",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-seedream-5-0-pro-260628",
    },
    "openai-compatible": {
        "provider": "openai-compatible",
        "base_url": "",
        "model": "",
    },
}


def default_env_file() -> Path:
    """Return one stable per-user config path without requiring shell setup."""
    configured_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    root = Path(configured_home).expanduser() if configured_home else Path.home() / ".config"
    return root / "wonderbell-imagegen" / ".env"


class ConfigureError(RuntimeError):
    """Configuration input or file update failure."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a private .env for openai-compatible-imagegen without echoing the key."
    )
    parser.add_argument("profile", choices=tuple(PRESETS), help="Provider preset")
    parser.add_argument("--env-file", type=Path, default=default_env_file())
    parser.add_argument("--base-url", help="Override the preset API root")
    parser.add_argument("--model", help="Override the preset model ID")
    parser.add_argument(
        "--api-key-env",
        help="Read the key from this environment variable instead of prompting",
    )
    parser.add_argument(
        "--keep-existing-key",
        action="store_true",
        help="Reuse a non-empty IMAGEGEN_API_KEY already in the target file",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable completion details",
    )
    return parser.parse_args()


def parse_env_file(path: Path) -> tuple[list[str], Dict[str, str]]:
    if not path.exists():
        return [], {}
    if path.is_symlink() or not path.is_file():
        raise ConfigureError(f"refusing non-regular env file: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    values: Dict[str, str] = {}
    for line in lines:
        match = ASSIGNMENT.match(line)
        if not match:
            continue
        name = match.group("name")
        value = line.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[name] = value
    return lines, values


def require_single_line(value: str, name: str) -> str:
    if not value or value != value.strip() or "\n" in value or "\r" in value:
        raise ConfigureError(f"{name} must be a non-empty single-line value")
    return value


def validate_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigureError("base URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigureError("base URL cannot contain credentials, query, or fragment")
    local = (parsed.hostname or "").lower() in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not local:
        raise ConfigureError("base URL must use HTTPS outside localhost")
    return value.rstrip("/")


def read_api_key(args: argparse.Namespace, existing: Dict[str, str]) -> str:
    current = existing.get("IMAGEGEN_API_KEY", "").strip()
    if args.api_key_env:
        if not ENV_NAME.fullmatch(args.api_key_env):
            raise ConfigureError("--api-key-env must be an environment variable name")
        value = os.environ.get(args.api_key_env, "")
        if not value:
            raise ConfigureError(f"environment variable {args.api_key_env} is empty or missing")
        return require_single_line(value, "API key")
    if args.keep_existing_key:
        if not current:
            raise ConfigureError("target file has no existing IMAGEGEN_API_KEY to keep")
        return current
    suffix = " (press Enter to keep the existing key)" if current else ""
    try:
        value = getpass.getpass(
            f"火山 Ark API Key（粘贴后不会显示，这是正常的）{suffix}: "
        )
    except (EOFError, KeyboardInterrupt) as exc:
        raise ConfigureError("API key input was cancelled") from exc
    if not value and current:
        return current
    return require_single_line(value, "API key")


def prompt_value(label: str, existing: str = "") -> str:
    suffix = f" [{existing}]" if existing else ""
    try:
        value = input(f"{label}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt) as exc:
        raise ConfigureError(f"{label} input was cancelled") from exc
    return value or existing


def merge_lines(lines: Iterable[str], updates: Dict[str, str]) -> list[str]:
    result = []
    written = set()
    for line in lines:
        match = ASSIGNMENT.match(line)
        if not match or match.group("name") not in updates:
            result.append(line)
            continue
        name = match.group("name")
        if name not in written:
            result.append(f"{name}={updates[name]}")
            written.add(name)
    if result and result[-1] != "":
        result.append("")
    for name, value in updates.items():
        if name not in written:
            result.append(f"{name}={value}")
    return result


def atomic_write(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as target:
            temporary = Path(target.name)
            target.write("\n".join(lines).rstrip("\n") + "\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        if temporary and temporary.exists():
            temporary.unlink()
        raise


def run() -> int:
    args = parse_args()
    path = args.env_file.expanduser().resolve()
    lines, existing = parse_env_file(path)
    preset = PRESETS[args.profile]
    api_key = read_api_key(args, existing)
    base_url = args.base_url or preset["base_url"] or existing.get("IMAGEGEN_BASE_URL", "")
    if not base_url:
        base_url = prompt_value("Base URL")
    model = args.model or preset["model"] or existing.get("IMAGEGEN_MODEL", "")
    if not model:
        model = prompt_value("Model ID")
    updates = {
        "IMAGEGEN_PROVIDER": preset["provider"],
        "IMAGEGEN_API_KEY": api_key,
        "IMAGEGEN_BASE_URL": validate_base_url(require_single_line(base_url, "base URL")),
        "IMAGEGEN_MODEL": require_single_line(model, "model ID"),
        "IMAGEGEN_TIMEOUT_SECONDS": existing.get("IMAGEGEN_TIMEOUT_SECONDS", "180") or "180",
        "IMAGEGEN_GENERATIONS_PATH": existing.get(
            "IMAGEGEN_GENERATIONS_PATH", "/images/generations"
        ) or "/images/generations",
    }
    atomic_write(path, merge_lines(lines, updates))
    result = {
        "status": "configured",
        "env_file": str(path),
        "provider": updates["IMAGEGEN_PROVIDER"],
        "base_url": updates["IMAGEGEN_BASE_URL"],
        "model": updates["IMAGEGEN_MODEL"],
        "api_key": "configured",
        "file_mode": "0600",
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n配置完成。")
        print("以后直接告诉 Codex 想生成什么图片即可。")
        print(f"配置已安全保存在：{path}")
    return 0


def main() -> int:
    try:
        return run()
    except ConfigureError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
