#!/usr/bin/env python3
"""Generate images through OpenAI-compatible or Volcengine Ark Images APIs."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import mimetypes
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
SAFE_FIELD = re.compile(r"^[A-Za-z0-9_.\[\]-]+$")


class ImageGenError(RuntimeError):
    """Configuration, request, or response failure."""


def default_env_file() -> Path:
    configured_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    root = Path(configured_home).expanduser() if configured_home else Path.home() / ".config"
    return root / "wonderbell-imagegen" / ".env"


def resolve_env_file(requested: Optional[Path]) -> Path:
    if requested is not None:
        return requested.expanduser().resolve()
    local = Path(".env").resolve()
    return local if local.is_file() else default_env_file().resolve()


@dataclass(frozen=True)
class Config:
    provider: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int
    generations_path: str
    edits_path: str
    reference_field: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check or execute one compatible image generation request."
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="Validate locally; do not call the API")
    action.add_argument("--execute", action="store_true", help="Call the configured API")
    prompt = parser.add_mutually_exclusive_group(required=True)
    prompt.add_argument("--prompt", help="Prompt text; prefer --prompt-file for long prompts")
    prompt.add_argument("--prompt-file", type=Path, help="UTF-8 prompt text file")
    parser.add_argument("--reference", action="append", default=[], type=Path)
    parser.add_argument("--mode", choices=("auto", "generations", "edits"), default="auto")
    parser.add_argument("--model")
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--size")
    parser.add_argument("--quality")
    parser.add_argument("--background")
    parser.add_argument("--output-format", choices=("png", "jpeg", "jpg", "webp"))
    parser.add_argument("--extra-file", type=Path, help="Provider-specific JSON object")
    parser.add_argument("--idempotency-key", help="Optional stable request key, mainly for Ark")
    parser.add_argument("--name", default="image", help="Safe label for the run directory")
    parser.add_argument("--output-dir", type=Path, default=Path("generated-images"))
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Private config file; defaults to .env or the one-time user setup",
    )
    return parser.parse_args()


def load_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    values: Dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ImageGenError(f"{path}:{number}: expected NAME=value")
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if not name:
            raise ImageGenError(f"{path}:{number}: environment name is empty")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[name] = value
    return values


def setting(
    file_values: Mapping[str, str], primary: str, fallback: str = "", default: str = ""
) -> str:
    for name in (primary, fallback):
        if name:
            value = os.environ.get(name, file_values.get(name, "")).strip()
            if value:
                return value
    return default


def positive_int(value: str, name: str) -> int:
    try:
        result = int(value)
    except ValueError as exc:
        raise ImageGenError(f"{name} must be an integer") from exc
    if result < 1:
        raise ImageGenError(f"{name} must be at least 1")
    return result


def validate_base_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ImageGenError("IMAGEGEN_BASE_URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ImageGenError("IMAGEGEN_BASE_URL cannot contain credentials, query, or fragment")
    local = (parsed.hostname or "").lower() in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not local:
        raise ImageGenError("IMAGEGEN_BASE_URL must use HTTPS outside localhost")
    return value.rstrip("/")


def validate_endpoint_path(value: str, name: str) -> str:
    if not value.startswith("/") or urllib.parse.urlsplit(value).netloc:
        raise ImageGenError(f"{name} must be an API path such as /images/generations")
    if "?" in value or "#" in value:
        raise ImageGenError(f"{name} cannot contain a query or fragment")
    return value


def load_config(path: Path) -> Config:
    values = load_env_file(path)
    provider = setting(values, "IMAGEGEN_PROVIDER", default="openai-compatible")
    if provider not in {"openai-compatible", "ark"}:
        raise ImageGenError("IMAGEGEN_PROVIDER must be openai-compatible or ark")
    api_key = setting(values, "IMAGEGEN_API_KEY", "OPENAI_API_KEY")
    base_url = setting(values, "IMAGEGEN_BASE_URL", "OPENAI_BASE_URL")
    if not api_key or not base_url:
        raise ImageGenError(
            "image generation is not configured; run setup-seedream.command once"
        )
    reference_field = setting(values, "IMAGEGEN_REFERENCE_FIELD", default="image[]")
    if not SAFE_FIELD.fullmatch(reference_field):
        raise ImageGenError("IMAGEGEN_REFERENCE_FIELD contains unsupported characters")
    return Config(
        provider=provider,
        api_key=api_key,
        base_url=validate_base_url(base_url),
        model=setting(values, "IMAGEGEN_MODEL", "OPENAI_IMAGE_MODEL"),
        timeout_seconds=positive_int(
            setting(values, "IMAGEGEN_TIMEOUT_SECONDS", default="180"),
            "IMAGEGEN_TIMEOUT_SECONDS",
        ),
        generations_path=validate_endpoint_path(
            setting(values, "IMAGEGEN_GENERATIONS_PATH", default="/images/generations"),
            "IMAGEGEN_GENERATIONS_PATH",
        ),
        edits_path=validate_endpoint_path(
            setting(values, "IMAGEGEN_EDITS_PATH", default="/images/edits"),
            "IMAGEGEN_EDITS_PATH",
        ),
        reference_field=reference_field,
    )


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        try:
            value = args.prompt_file.expanduser().resolve().read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ImageGenError(f"prompt file not found: {args.prompt_file}") from exc
    else:
        value = args.prompt or ""
    value = value.strip()
    if not value:
        raise ImageGenError("prompt must not be empty")
    return value


def read_extra(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {}
    resolved = path.expanduser().resolve()
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ImageGenError(f"extra JSON file not found: {resolved}") from exc
    except json.JSONDecodeError as exc:
        raise ImageGenError(f"{resolved}:{exc.lineno}: invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ImageGenError("extra JSON must be an object")
    protected = {
        "prompt", "model", "n", "size", "quality", "background", "output_format", "image"
    }
    conflicts = sorted(protected.intersection(value))
    if conflicts:
        raise ImageGenError(f"extra JSON cannot replace protected fields: {', '.join(conflicts)}")
    return value


def resolve_references(paths: Iterable[Path]) -> Tuple[Path, ...]:
    resolved = []
    for item in paths:
        path = item.expanduser().resolve()
        if not path.is_file():
            raise ImageGenError(f"reference image not found: {path}")
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            raise ImageGenError(f"unsupported reference image: {path}")
        resolved.append(path)
    return tuple(resolved)


def resolve_mode(provider: str, requested: str, references: Tuple[Path, ...]) -> str:
    if provider == "ark":
        if requested == "edits":
            raise ImageGenError("Ark reference images use generations JSON, not edits multipart")
        return "generations"
    mode = "edits" if requested == "auto" and references else (
        "generations" if requested == "auto" else requested
    )
    if mode == "edits" and not references:
        raise ImageGenError("edits mode requires at least one --reference")
    if mode == "generations" and references:
        raise ImageGenError("generations mode does not upload references; use auto or edits")
    return mode


def image_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def build_payload(
    args: argparse.Namespace,
    config: Config,
    prompt: str,
    references: Tuple[Path, ...],
) -> Dict[str, Any]:
    if args.n < 1:
        raise ImageGenError("--n must be at least 1")
    if config.provider == "ark" and args.n != 1:
        raise ImageGenError("Ark profile currently supports one output per request; use --n 1")
    payload: Dict[str, Any] = {"prompt": prompt}
    if config.provider != "ark":
        payload["n"] = args.n
    model = (args.model or config.model).strip()
    if config.provider == "ark" and not model:
        raise ImageGenError("Ark profile requires IMAGEGEN_MODEL or --model")
    if model:
        payload["model"] = model
    fields = [(args.size, "size"), (args.output_format, "output_format")]
    if config.provider != "ark":
        fields.extend([(args.quality, "quality"), (args.background, "background")])
    elif args.quality or args.background:
        raise ImageGenError("Ark profile does not map --quality or --background")
    for argument, field in fields:
        if argument:
            payload[field] = argument
    if config.provider == "ark":
        if references:
            payload["image"] = [image_data_url(path) for path in references]
        payload.setdefault("response_format", "b64_json")
        payload.setdefault("output_format", "png")
        payload.setdefault("watermark", False)
    payload.update(read_extra(args.extra_file))
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def multipart_body(
    fields: Mapping[str, Any], images: Iterable[Path], field_name: str
) -> Tuple[bytes, str]:
    boundary = f"wonderbell-imagegen-{secrets.token_hex(16)}"
    body = bytearray()

    def line(value: bytes = b"") -> None:
        body.extend(value)
        body.extend(b"\r\n")

    for name, value in fields.items():
        if value is None or value == "":
            continue
        line(f"--{boundary}".encode())
        line(f'Content-Disposition: form-data; name="{name}"'.encode())
        line()
        encoded = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        line(encoded.encode("utf-8"))
    for image in images:
        mime = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
        line(f"--{boundary}".encode())
        line(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{image.name}"'.encode()
        )
        line(f"Content-Type: {mime}".encode())
        line()
        body.extend(image.read_bytes())
        body.extend(b"\r\n")
    line(f"--{boundary}--".encode())
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def sanitize_request_payload(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("data:image/") and ";base64," in value:
        return "<data-url omitted; see reference_images>"
    if isinstance(value, dict):
        return {key: sanitize_request_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_request_payload(item) for item in value]
    return value


def request_json(
    url: str,
    payload: Mapping[str, Any],
    references: Tuple[Path, ...],
    mode: str,
    provider: str,
    idempotency_key: Optional[str],
) -> Dict[str, Any]:
    return {
        "provider": provider,
        "endpoint": url,
        "mode": mode,
        "idempotency_key": idempotency_key,
        "payload": sanitize_request_payload(payload),
        "reference_images": [
            {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in references
        ],
    }


def post(
    url: str,
    payload: Mapping[str, Any],
    references: Tuple[Path, ...],
    mode: str,
    config: Config,
    idempotency_key: Optional[str],
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Accept": "application/json",
        "User-Agent": "wonderbell-skills/openai-compatible-imagegen/1.0",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    if mode == "edits":
        body, content_type = multipart_body(payload, references, config.reference_field)
    else:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        content_type = "application/json"
    headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            response_body = response.read()
            response_type = response.headers.get_content_type()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:4000]
        detail = detail.replace(config.api_key, "<redacted>")
        uncertainty = "; result may be uncertain and should not be retried blindly" if exc.code >= 500 else ""
        raise ImageGenError(f"API returned HTTP {exc.code}: {detail}{uncertainty}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise ImageGenError(
            f"API request failed; result may be uncertain: {getattr(exc, 'reason', exc)}"
        ) from exc
    if response_type != "application/json":
        raise ImageGenError(f"expected JSON response, got {response_type}")
    try:
        value = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise ImageGenError("API response is not valid JSON") from exc
    if not isinstance(value, dict):
        raise ImageGenError("API response must be a JSON object")
    return value


def response_items(response: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in ("data", "images"):
        value = response.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def download_image(item: Mapping[str, Any], timeout: int) -> Tuple[bytes, str]:
    encoded = item.get("b64_json") or item.get("image_base64") or item.get("b64")
    if isinstance(encoded, str) and encoded:
        if encoded.startswith("data:") and ";base64," in encoded:
            header, encoded = encoded.split(",", 1)
            mime = header[5:].split(";", 1)[0]
        else:
            mime = "application/octet-stream"
        try:
            return base64.b64decode(encoded, validate=True), mime
        except (ValueError, binascii.Error) as exc:
            raise ImageGenError("API returned invalid base64 image data") from exc
    url = item.get("url")
    if isinstance(url, str) and url:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            raise ImageGenError("API returned an unsupported image URL")
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                return response.read(), response.headers.get_content_type()
        except (urllib.error.URLError, OSError) as exc:
            raise ImageGenError(f"image download failed: {getattr(exc, 'reason', exc)}") from exc
    raise ImageGenError("API response item has neither base64 image data nor a URL")


def detect_image(data: bytes, content_type: str, requested_format: Optional[str]) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    fallback = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }.get(content_type)
    if fallback:
        return fallback
    if requested_format:
        return ".jpg" if requested_format in {"jpg", "jpeg"} else f".{requested_format}"
    raise ImageGenError("provider returned bytes that are not a recognized PNG, JPEG, or WebP image")


def sanitize_response(value: Any) -> Any:
    if isinstance(value, dict):
        clean: Dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in {"b64_json", "image_base64", "b64"} and isinstance(item, str):
                clean[key] = "<omitted after local image save>"
            elif key.lower() == "url" and isinstance(item, str):
                parsed = urllib.parse.urlsplit(item)
                clean[key] = urllib.parse.urlunsplit(
                    (parsed.scheme, parsed.netloc, parsed.path, "", "")
                )
            else:
                clean[key] = sanitize_response(item)
        return clean
    if isinstance(value, list):
        return [sanitize_response(item) for item in value]
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run() -> int:
    args = parse_args()
    if not SAFE_NAME.fullmatch(args.name):
        raise ImageGenError("--name must be 1-80 safe filename characters")
    config = load_config(resolve_env_file(args.env_file))
    prompt = read_prompt(args)
    references = resolve_references(args.reference)
    mode = resolve_mode(config.provider, args.mode, references)
    payload = build_payload(args, config, prompt, references)
    path = config.edits_path if mode == "edits" else config.generations_path
    url = f"{config.base_url}{path}"
    idempotency_key = args.idempotency_key
    if config.provider == "ark" and not idempotency_key:
        idempotency_key = (
            f"imagegen-{secrets.token_urlsafe(18)}" if args.execute else "<generated-on-execute>"
        )
    record = request_json(
        url, payload, references, mode, config.provider, idempotency_key
    )

    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "action": "check-only",
                    "provider": config.provider,
                    "mode": mode,
                    "endpoint": url,
                    "model": payload.get("model"),
                    "references": len(references),
                    "requested_images": args.n,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f%z")
    run_dir = args.output_dir.expanduser().resolve() / args.name / timestamp
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(run_dir / "request.json", record)
    run_record: Dict[str, Any] = {
        "schema_version": 1,
        "status": "in_progress",
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "provider": config.provider,
        "mode": mode,
        "endpoint": url,
        "outputs": [],
    }
    write_json(run_dir / "run.json", run_record)
    began = time.monotonic()
    try:
        response = post(url, payload, references, mode, config, idempotency_key)
        items = response_items(response)
        if not items:
            raise ImageGenError("API response contains no image items")
        write_json(run_dir / "response.json", sanitize_response(response))
        for index, item in enumerate(items, 1):
            data, content_type = download_image(item, config.timeout_seconds)
            requested_format = str(payload.get("output_format") or "") or None
            suffix = detect_image(data, content_type, requested_format)
            image_path = run_dir / f"{index:02d}{suffix}"
            image_path.write_bytes(data)
            run_record["outputs"].append(
                {
                    "path": str(image_path),
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        run_record["status"] = "success"
    except Exception as exc:
        run_record["status"] = "failed_or_uncertain"
        write_json(run_dir / "error.json", {"type": type(exc).__name__, "message": str(exc)})
        raise ImageGenError(f"{exc} (records kept in {run_dir})") from exc
    finally:
        run_record["duration_seconds"] = round(time.monotonic() - began, 3)
        run_record["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        write_json(run_dir / "run.json", run_record)
    print(
        json.dumps(
            {"status": "success", "run_dir": str(run_dir), "outputs": run_record["outputs"]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    try:
        return run()
    except ImageGenError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
