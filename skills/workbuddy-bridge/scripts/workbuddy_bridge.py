#!/usr/bin/env python3
"""
workbuddy_bridge.py - Read local WorkBuddy Desktop sessions and drive sessions via CodeBuddy CLI.

Zero external dependencies (Python 3 standard library only).
Respects $WORKBUDDY_HOME (defaults to ~/.workbuddy).
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


BUSY_STATUSES = {"working", "running", "in_progress", "streaming", "pending"}
SYSTEM_REMINDER_RE = re.compile(r"<system-reminder\b[^>]*>.*?</system-reminder>", re.DOTALL | re.IGNORECASE)
USER_QUERY_RE = re.compile(r"<user_query>(.*?)</user_query>", re.DOTALL | re.IGNORECASE)


def workbuddy_home() -> Path:
    return Path(os.environ.get("WORKBUDDY_HOME", "~/.workbuddy")).expanduser()


def fmt_ts(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        try:
            return dt.datetime.fromtimestamp(ts).astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(value)
    text = str(value)
    if text.endswith("Z"):
        try:
            parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return text
    return text


def to_epoch_seconds(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        ts = float(value)
        return ts / 1000.0 if ts > 1e12 else ts
    text = str(value)
    try:
        ts = float(text)
        return ts / 1000.0 if ts > 1e12 else ts
    except ValueError:
        pass
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def compact_one_line(text: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if max_len > 0 and len(cleaned) > max_len:
        return cleaned[: max_len - 1] + "…"
    return cleaned


def truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated, total {len(text)} chars]"


def encode_cwd_slug(cwd: str) -> str:
    norm = (cwd or "").replace("\\", "/").strip()
    if not norm:
        return ""
    if len(norm) >= 2 and norm[1] == ":":
        rest = norm[2:].lstrip("/")
        rest = re.sub(r"[^A-Za-z0-9._-]", "-", rest)
        return f"{norm[0].lower()}-{rest}" if rest else norm[0].lower()
    rest = norm.lstrip("/")
    return re.sub(r"[^A-Za-z0-9._-]", "-", rest)


def build_transcript_index(root: Path) -> dict[str, Path]:
    """Map session_id -> transcript Path across ~/.workbuddy/projects/*/*.jsonl."""
    index: dict[str, Path] = {}
    projects_dir = root / "projects"
    if not projects_dir.is_dir():
        return index
    for p in projects_dir.glob("*/*.jsonl"):
        sid = p.stem
        # If duplicates ever exist, prefer most recently modified
        if sid not in index or p.stat().st_mtime > index[sid].stat().st_mtime:
            index[sid] = p
    return index


def find_transcript_path(
    root: Path,
    session_id: str,
    cwd: str | None = None,
    transcript_index: dict[str, Path] | None = None,
) -> Path | None:
    if cwd:
        slug = encode_cwd_slug(cwd)
        if slug:
            direct = root / "projects" / slug / f"{session_id}.jsonl"
            if direct.is_file():
                return direct
    if transcript_index is not None:
        hit = transcript_index.get(session_id)
        if hit and hit.is_file():
            return hit
    projects_dir = root / "projects"
    if projects_dir.is_dir():
        matches = list(projects_dir.glob(f"*/{session_id}.jsonl"))
        if matches:
            matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return matches[0]
    return None


def is_transcript_actively_writing(transcript_path: Path | None, window_sec: float = 10.0) -> bool:
    """Heuristic: check if transcript was modified within window_sec without ending on assistant message."""
    if not transcript_path or not transcript_path.is_file():
        return False
    try:
        st = transcript_path.stat()
    except OSError:
        return False
    if (time.time() - st.st_mtime) > window_sec:
        return False

    try:
        size = st.st_size
        read_size = min(size, 32768)
        with transcript_path.open("rb") as f:
            if size > read_size:
                f.seek(size - read_size)
            chunk = f.read(read_size).decode("utf-8", errors="replace")
    except OSError:
        return False

    last_event: tuple[str | None, str | None] = (None, None)
    for line in chunk.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = obj.get("type")
        if etype in ("message", "function_call", "function_call_result", "reasoning"):
            last_event = (etype, obj.get("role"))

    etype, role = last_event
    if etype == "message" and role == "assistant":
        return False
    return etype is not None


def list_sessions_from_db(
    root: Path,
    include_deleted: bool = False,
) -> list[dict[str, Any]] | None:
    db_path = root / "workbuddy.db"
    if not db_path.is_file():
        return None
    try:
        con = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
    except sqlite3.Error:
        return None

    try:
        cols = {row["name"] for row in con.execute("PRAGMA table_info(sessions)")}
        if not cols:
            return None

        spaces_map: dict[str, dict[str, Any]] = {}
        try:
            for srow in con.execute("SELECT id, name, primary_folder_path, status FROM spaces"):
                spaces_map[str(srow["id"])] = dict(srow)
        except sqlite3.Error:
            pass

        usage_map: dict[str, dict[str, Any]] = {}
        try:
            for urow in con.execute("SELECT session_id, used, size, updated_at FROM session_usage"):
                usage_map[str(urow["session_id"])] = dict(urow)
        except sqlite3.Error:
            pass

        wanted = [
            "id",
            "cwd",
            "user_id",
            "title",
            "custom_title",
            "status",
            "created_at",
            "updated_at",
            "last_activity_at",
            "deleted_at",
            "mode",
            "source_mode",
            "model",
            "permission_mode",
            "project_id",
            "space_id",
            "group_id",
            "group_title",
            "transport",
            "is_background_automation",
            "thought_level",
            "context_window",
        ]
        select_cols = [c for c in wanted if c in cols]
        where_sql = "" if include_deleted or "deleted_at" not in cols else "WHERE deleted_at IS NULL"
        order_col = "updated_at" if "updated_at" in cols else "created_at"
        sql = f"SELECT {', '.join(select_cols)} FROM sessions {where_sql} ORDER BY {order_col} DESC"

        transcript_index = build_transcript_index(root)
        rows: list[dict[str, Any]] = []
        for row in con.execute(sql):
            item = dict(row)
            sid = str(item.get("id") or "")
            cwd = str(item.get("cwd") or "")
            tpath = find_transcript_path(root, sid, cwd=cwd, transcript_index=transcript_index)
            space_id = str(item.get("space_id") or "")
            space_info = spaces_map.get(space_id) or {}
            usage_info = usage_map.get(sid) or {}

            status_raw = str(item.get("status") or "").strip()
            working = status_raw.lower() in BUSY_STATUSES
            active_write = is_transcript_actively_writing(tpath)

            item["transcript_path"] = str(tpath) if tpath else ""
            item["has_transcript"] = bool(tpath)
            item["space_name"] = space_info.get("name") or ""
            item["display_title"] = (
                item.get("custom_title")
                or item.get("title")
                or (tpath.stem if tpath else "(untitled)")
            )
            item["working"] = working
            item["active_write"] = active_write
            item["busy"] = working or active_write
            item["deleted"] = item.get("deleted_at") is not None
            if usage_info:
                item["tokens_used"] = usage_info.get("used")
                item["context_size"] = usage_info.get("size")
            rows.append(item)
        return rows
    except sqlite3.Error:
        return None
    finally:
        con.close()


def scan_sessions_from_files(root: Path) -> list[dict[str, Any]]:
    projects_dir = root / "projects"
    if not projects_dir.is_dir():
        return []
    files = list(projects_dir.glob("*/*.jsonl"))
    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

    rows: list[dict[str, Any]] = []
    for path in files:
        sid = path.stem
        title = ""
        cwd = ""
        model = ""
        created_at: Any = None
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for _ in range(40):
                    line = f.readline()
                    if not line:
                        break
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not created_at and obj.get("timestamp"):
                        created_at = obj.get("timestamp")
                    if not cwd and obj.get("cwd"):
                        cwd = str(obj.get("cwd"))
                    if obj.get("type") == "ai-title" and obj.get("aiTitle"):
                        title = str(obj.get("aiTitle"))
                    if obj.get("type") == "message" and not title and obj.get("role") == "user":
                        t = extract_content_text(obj.get("content"))
                        if t:
                            title = compact_one_line(t, 80)
                    pd = obj.get("providerData")
                    if isinstance(pd, dict) and not model:
                        model = str(pd.get("requestModelId") or pd.get("model") or "")
        except OSError:
            continue

        stat = path.stat()
        active_write = is_transcript_actively_writing(path)
        rows.append(
            {
                "id": sid,
                "cwd": cwd,
                "title": title or path.stem,
                "display_title": title or path.stem,
                "status": "unknown",
                "created_at": created_at or int(stat.st_ctime * 1000),
                "updated_at": int(stat.st_mtime * 1000),
                "model": model or None,
                "space_name": "",
                "project_id": "",
                "transcript_path": str(path),
                "has_transcript": True,
                "working": False,
                "active_write": active_write,
                "busy": active_write,
                "deleted": False,
            }
        )
    return rows


def load_sessions(root: Path, include_deleted: bool = False) -> list[dict[str, Any]]:
    rows = list_sessions_from_db(root, include_deleted=include_deleted)
    if rows is not None:
        return rows
    return scan_sessions_from_files(root)


def filter_sessions(
    rows: list[dict[str, Any]],
    cwd: str | None = None,
    query: str | None = None,
    space: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    result = rows
    if cwd:
        needle = cwd.lower()
        result = [r for r in result if needle in str(r.get("cwd") or "").lower()]
    if space:
        needle = space.lower()
        result = [
            r
            for r in result
            if needle in str(r.get("space_name") or "").lower()
            or needle in str(r.get("space_id") or "").lower()
            or needle in str(r.get("group_title") or "").lower()
            or needle in str(r.get("project_id") or "").lower()
        ]
    if status:
        needle = status.lower()
        result = [r for r in result if str(r.get("status") or "").lower() == needle]
    if query:
        needle = query.lower()
        filtered = []
        for r in result:
            haystack = " ".join(
                str(r.get(k) or "")
                for k in (
                    "id",
                    "title",
                    "custom_title",
                    "display_title",
                    "cwd",
                    "space_name",
                    "group_title",
                    "model",
                    "project_id",
                )
            ).lower()
            if needle in haystack:
                filtered.append(r)
        result = filtered
    return result


def resolve_session(
    root: Path,
    target: str | None,
    use_last: bool = False,
    cwd: str | None = None,
    space: str | None = None,
) -> dict[str, Any]:
    rows = load_sessions(root, include_deleted=True)
    if use_last:
        candidates = [r for r in rows if not r.get("deleted")]
        candidates = filter_sessions(candidates, cwd=cwd, space=space)
        if not candidates:
            raise SystemExit("No matching active WorkBuddy session found.")
        return candidates[0]

    if not target:
        raise SystemExit("Specify a session id/prefix/title or pass --last.")

    target_lower = target.lower()
    # 1. Exact ID match
    for r in rows:
        if str(r.get("id", "")).lower() == target_lower:
            return r
    # 2. Exact title / custom_title match
    exact_titles = [
        r
        for r in rows
        if str(r.get("display_title") or "").lower() == target_lower
        or str(r.get("title") or "").lower() == target_lower
    ]
    if len(exact_titles) == 1:
        return exact_titles[0]
    # 3. ID prefix match
    prefix_matches = [r for r in rows if str(r.get("id", "")).lower().startswith(target_lower)]
    if len(prefix_matches) == 1:
        return prefix_matches[0]
    if len(prefix_matches) > 1:
        ids = ", ".join(str(r["id"]) for r in prefix_matches[:5])
        raise SystemExit(f"Ambiguous session prefix '{target}'. Matches: {ids}")
    # 4. Substring match on title/cwd/space
    sub_matches = filter_sessions(rows, cwd=cwd, space=space, query=target)
    if len(sub_matches) == 1:
        return sub_matches[0]
    if len(sub_matches) > 1:
        preview = "\n".join(
            f"  - {r['id']}  [{fmt_ts(r.get('updated_at'))}]  {compact_one_line(str(r.get('display_title', '')), 70)}"
            for r in sub_matches[:8]
        )
        raise SystemExit(f"Multiple sessions matched '{target}'. Please specify an exact session ID:\n{preview}")

    # 5. Direct JSONL path fallback
    maybe_path = Path(target).expanduser()
    if maybe_path.is_file():
        return {
            "id": maybe_path.stem,
            "transcript_path": str(maybe_path),
            "has_transcript": True,
            "display_title": maybe_path.name,
            "cwd": "",
            "status": "unknown",
            "busy": False,
        }

    raise SystemExit(f"WorkBuddy session not found: {target}")


def extract_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        if "text" in content:
            return str(content.get("text") or "").strip()
        return json.dumps(content, ensure_ascii=False)
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            if block.strip():
                parts.append(block.strip())
        elif isinstance(block, dict):
            btype = str(block.get("type") or "")
            if btype in ("input_text", "output_text", "text"):
                txt = str(block.get("text") or "").strip()
                if txt:
                    parts.append(txt)
            elif btype in ("image_blob_ref", "input_image", "image_url", "image"):
                fname = block.get("original_filename") or block.get("mime") or ""
                parts.append(f"[image: {fname}]" if fname else "[image]")
            elif "text" in block:
                txt = str(block.get("text") or "").strip()
                if txt:
                    parts.append(txt)
    return "\n\n".join(parts).strip()


def clean_user_boilerplate(text: str) -> str:
    cleaned = SYSTEM_REMINDER_RE.sub("", text or "")
    cleaned = USER_QUERY_RE.sub(lambda m: m.group(1).strip(), cleaned)
    return cleaned.strip()


def parse_transcript_messages(
    transcript_path: Path,
    include_tools: bool = False,
    include_reasoning: bool = False,
    final_only: bool = False,
    include_boilerplate: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    meta: dict[str, Any] = {}
    items: list[dict[str, Any]] = []

    if not transcript_path.is_file():
        raise SystemExit(f"Transcript file does not exist: {transcript_path}")

    with transcript_path.open("r", encoding="utf-8", errors="replace") as f:
        for line_no, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue

            etype = obj.get("type")
            ts = obj.get("timestamp")
            if obj.get("sessionId") and not meta.get("id"):
                meta["id"] = obj.get("sessionId")
            if obj.get("cwd") and not meta.get("cwd"):
                meta["cwd"] = obj.get("cwd")

            if etype == "session-meta":
                if isinstance(obj.get("meta"), dict):
                    meta.setdefault("session_meta", {}).update(obj["meta"])
                continue

            if etype == "ai-title" and obj.get("aiTitle"):
                meta["ai_title"] = obj.get("aiTitle")
                continue

            if etype == "message":
                role = obj.get("role")
                if role not in ("user", "assistant"):
                    continue
                text = extract_content_text(obj.get("content"))
                if role == "user" and not include_boilerplate:
                    text = clean_user_boilerplate(text)
                if not text:
                    continue
                pd = obj.get("providerData") if isinstance(obj.get("providerData"), dict) else {}
                model = pd.get("requestModelId") or pd.get("model") or ""
                req_id = pd.get("conversationRequestId") or ""
                items.append(
                    {
                        "kind": "message",
                        "role": role,
                        "model": model,
                        "request_id": req_id,
                        "timestamp": ts,
                        "line": line_no,
                        "text": text,
                    }
                )
            elif include_reasoning and etype == "reasoning":
                text = extract_content_text(obj.get("rawContent") or obj.get("content"))
                if not text:
                    continue
                items.append(
                    {
                        "kind": "reasoning",
                        "role": "reasoning",
                        "timestamp": ts,
                        "line": line_no,
                        "text": text,
                    }
                )
            elif include_tools and etype == "function_call":
                name = str(obj.get("name") or "tool")
                raw_args = obj.get("arguments")
                arg_text = raw_args if isinstance(raw_args, str) else json.dumps(raw_args, ensure_ascii=False)
                items.append(
                    {
                        "kind": "tool_call",
                        "role": "tool_call",
                        "name": name,
                        "call_id": obj.get("callId"),
                        "timestamp": ts,
                        "line": line_no,
                        "text": arg_text or "",
                    }
                )
            elif include_tools and etype == "function_call_result":
                name = str(obj.get("name") or "")
                out_text = extract_content_text(obj.get("output"))
                status = obj.get("status")
                prefix = f"[{status}] " if status and status != "completed" else ""
                items.append(
                    {
                        "kind": "tool_output",
                        "role": "tool_output",
                        "name": name,
                        "call_id": obj.get("callId"),
                        "timestamp": ts,
                        "line": line_no,
                        "text": prefix + out_text,
                    }
                )

    if final_only:
        # Keep every user message and only the final assistant message per user turn/request
        filtered: list[dict[str, Any]] = []
        pending_assistant: dict[str, Any] | None = None
        for it in items:
            if it["role"] == "user":
                if pending_assistant is not None:
                    filtered.append(pending_assistant)
                    pending_assistant = None
                filtered.append(it)
            elif it["role"] == "assistant":
                pending_assistant = it
            else:
                filtered.append(it)
        if pending_assistant is not None:
            filtered.append(pending_assistant)
        items = filtered

    return meta, items


def find_bundled_node(root: Path) -> str | None:
    versions_dir = root / "binaries" / "node" / "versions"
    if versions_dir.is_dir():
        candidates = sorted(
            [p for p in versions_dir.glob("*/node.exe") if p.is_file()]
            + [p for p in versions_dir.glob("*/bin/node") if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return str(candidates[0])
    return shutil.which("node")


def find_bundled_workbuddy_cli() -> Path | None:
    env_app = os.environ.get("WORKBUDDY_APP_DIR")
    candidates: list[Path] = []
    if env_app:
        candidates.append(Path(env_app).expanduser() / "resources" / "app.asar.unpacked" / "cli" / "bin" / "codebuddy")

    # Standard install paths on Windows / macOS
    local_app = os.environ.get("LOCALAPPDATA", "")
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    for base in (
        Path(r"D:\workbuddy"),
        Path(r"C:\workbuddy"),
        Path(prog_files) / "WorkBuddy",
        Path(local_app) / "Programs" / "WorkBuddy" if local_app else Path("__none__"),
        Path("/Applications/WorkBuddy.app/Contents"),
    ):
        candidates.append(base / "resources" / "app.asar.unpacked" / "cli" / "bin" / "codebuddy")
        candidates.append(base / "Resources" / "app.asar.unpacked" / "cli" / "bin" / "codebuddy")

    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def resolve_cli_runner(root: Path) -> dict[str, Any]:
    """
    Resolve how to invoke the underlying CodeBuddy CLI.
    Returns dict: {mode, cmd_prefix, env_extra, display_path}.
    """
    override = os.environ.get("WORKBUDDY_BRIDGE_BIN")
    if override:
        p = Path(override).expanduser()
        if p.is_file():
            return {
                "mode": "override",
                "cmd_prefix": [str(p)],
                "env_extra": {},
                "display_path": str(p),
            }
        raise SystemExit(f"WORKBUDDY_BRIDGE_BIN does not exist: {override}")

    # Prefer standalone installed CLI (supports interactive /login + full features)
    for name in ("codebuddy", "cbc"):
        found = shutil.which(name)
        if found:
            return {
                "mode": "standalone",
                "cmd_prefix": [found],
                "env_extra": {},
                "display_path": found,
            }

    # Fallback to WorkBuddy Desktop bundled lite-wb CLI
    bundled_cli = find_bundled_workbuddy_cli()
    if bundled_cli:
        node_exe = find_bundled_node(root)
        if not node_exe:
            raise SystemExit(
                f"Found bundled WorkBuddy CLI at {bundled_cli}, but could not locate Node.js executable."
            )
        return {
            "mode": "bundled-lite-wb",
            "cmd_prefix": [node_exe, str(bundled_cli)],
            "env_extra": {"CODEBUDDY_FORCE_LITE_WB_BUNDLE": "1"},
            "display_path": f"{node_exe} {bundled_cli}",
        }

    raise SystemExit(
        "Neither standalone `codebuddy` CLI nor bundled WorkBuddy CLI was found.\n"
        "Install with: npm install -g @tencent-ai/codebuddy-code\n"
        "Or set WORKBUDDY_APP_DIR / WORKBUDDY_BRIDGE_BIN."
    )


def get_cli_version(runner: dict[str, Any]) -> str:
    try:
        env = os.environ.copy()
        env.update(runner.get("env_extra") or {})
        proc = subprocess.run(
            runner["cmd_prefix"] + ["--version"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=10,
            env=env,
        )
        out = (proc.stdout or "").strip() or (proc.stderr or "").strip()
        return out.splitlines()[0] if out else "unknown"
    except Exception:
        return "unknown"


def cmd_doctor(args: argparse.Namespace) -> int:
    root = workbuddy_home()
    db_path = root / "workbuddy.db"
    rows = load_sessions(root, include_deleted=False) if root.is_dir() else []
    with_transcript = sum(1 for r in rows if r.get("has_transcript"))
    busy_count = sum(1 for r in rows if r.get("busy"))

    cli_info: dict[str, Any]
    try:
        runner = resolve_cli_runner(root)
        cli_info = {
            "available": True,
            "mode": runner["mode"],
            "path": runner["display_path"],
            "version": get_cli_version(runner),
        }
    except SystemExit as exc:
        cli_info = {"available": False, "error": str(exc)}

    auth_env = {
        "CODEBUDDY_API_KEY": bool(os.environ.get("CODEBUDDY_API_KEY")),
        "CODEBUDDY_AUTH_TOKEN": bool(os.environ.get("CODEBUDDY_AUTH_TOKEN")),
        "CODEBUDDY_INTERNET_ENVIRONMENT": os.environ.get("CODEBUDDY_INTERNET_ENVIRONMENT") or "",
        "CODEBUDDY_CONFIG_DIR": os.environ.get("CODEBUDDY_CONFIG_DIR") or "",
    }

    report = {
        "workbuddy_home": str(root),
        "home_exists": root.is_dir(),
        "db_exists": db_path.is_file(),
        "active_sessions": len(rows),
        "sessions_with_transcript": with_transcript,
        "busy_sessions": busy_count,
        "cli": cli_info,
        "auth_env": auth_env,
        "read_ready": root.is_dir() and (db_path.is_file() or len(rows) > 0),
        "send_ready_hint": (
            "Ready via env credentials"
            if (auth_env["CODEBUDDY_API_KEY"] or auth_env["CODEBUDDY_AUTH_TOKEN"])
            else (
                "Standalone CLI found; ensure `/login` has been completed with CODEBUDDY_CONFIG_DIR=" + str(root)
                if cli_info.get("mode") == "standalone"
                else "Bundled lite-wb CLI has no TUI /login; set CODEBUDDY_API_KEY (or install `@tencent-ai/codebuddy-code` and run `/login` with CODEBUDDY_CONFIG_DIR="
                + str(root)
                + ")"
            )
        ),
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"WorkBuddy Home : {report['workbuddy_home']} (exists={report['home_exists']})")
    print(f"SQLite DB      : {db_path} (exists={report['db_exists']})")
    print(f"Sessions       : {report['active_sessions']} active ({report['sessions_with_transcript']} with JSONL, {report['busy_sessions']} busy)")
    if cli_info.get("available"):
        print(f"CLI Runner     : [{cli_info['mode']}] v{cli_info['version']}")
        print(f"CLI Path       : {cli_info['path']}")
    else:
        print(f"CLI Runner     : NOT FOUND ({cli_info.get('error')})")
    print(
        f"Auth Env       : CODEBUDDY_API_KEY={'set' if auth_env['CODEBUDDY_API_KEY'] else 'unset'}, "
        f"CODEBUDDY_AUTH_TOKEN={'set' if auth_env['CODEBUDDY_AUTH_TOKEN'] else 'unset'}, "
        f"CODEBUDDY_INTERNET_ENVIRONMENT={auth_env['CODEBUDDY_INTERNET_ENVIRONMENT'] or '(unset)'}"
    )
    print(f"Send Readiness : {report['send_ready_hint']}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = workbuddy_home()
    rows = load_sessions(root, include_deleted=args.include_deleted)
    rows = filter_sessions(rows, cwd=args.cwd, query=args.query, space=args.space, status=args.status)
    total = len(rows)
    rows = rows[: args.limit] if args.limit > 0 else rows

    if args.json:
        print(json.dumps({"total": total, "sessions": rows}, ensure_ascii=False, indent=2))
        return 0

    if not rows:
        print("No matching WorkBuddy sessions found.")
        return 0

    print(f"Showing {len(rows)} of {total} WorkBuddy sessions (WORKBUDDY_HOME={root}):\n")
    for idx, r in enumerate(rows, start=1):
        ts = fmt_ts(r.get("updated_at") or r.get("last_activity_at") or r.get("created_at"))
        flags = []
        if r.get("working"):
            flags.append("WORKING")
        elif r.get("active_write"):
            flags.append("ACTIVE")
        status = str(r.get("status") or "")
        if status and status.lower() not in ("completed", "working", "unknown"):
            flags.append(status.upper())
        if r.get("deleted"):
            flags.append("DELETED")
        if not r.get("has_transcript"):
            flags.append("NO-JSONL")
        flag_str = f" [{' '.join(flags)}]" if flags else ""
        title = compact_one_line(str(r.get("display_title") or ""), 90)
        cwd = str(r.get("cwd") or "-")
        model = str(r.get("model") or "-")
        space = str(r.get("space_name") or r.get("group_title") or "")
        space_str = f"  | space: {space}" if space else ""
        print(f"{idx:2d}. {r['id']}  {ts}{flag_str}")
        print(f"    title : {title}")
        print(f"    cwd   : {cwd}  | model: {model}{space_str}")
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    root = workbuddy_home()
    session = resolve_session(root, args.target, use_last=args.last, cwd=args.cwd, space=args.space)
    tpath_str = str(session.get("transcript_path") or "")
    if not tpath_str:
        tpath = find_transcript_path(root, str(session.get("id") or ""), cwd=session.get("cwd"))
    else:
        tpath = Path(tpath_str).expanduser()
    if not tpath or not tpath.is_file():
        raise SystemExit(f"No transcript JSONL found for session {session.get('id')}")

    meta, items = parse_transcript_messages(
        tpath,
        include_tools=args.include_tools,
        include_reasoning=args.include_reasoning,
        final_only=args.final_only,
        include_boilerplate=args.include_boilerplate,
    )

    total_items = len(items)
    if args.offset > 0 or args.limit > 0:
        start = max(0, args.offset)
        end = start + args.limit if args.limit > 0 else total_items
        sliced = items[start:end]
        shown_range = (start + 1, min(end, total_items)) if sliced else (0, 0)
    elif args.last_turns > 0 and total_items > args.last_turns:
        sliced = items[-args.last_turns :]
        shown_range = (total_items - len(sliced) + 1, total_items)
    else:
        sliced = items
        shown_range = (1, total_items) if total_items else (0, 0)

    sid = str(session.get("id") or meta.get("id") or "")
    working = bool(session.get("working"))
    active_write = is_transcript_actively_writing(tpath)

    if args.json:
        out_items = []
        for it in sliced:
            copy = dict(it)
            copy["text"] = truncate_text(copy["text"], args.max_chars)
            out_items.append(copy)
        print(
            json.dumps(
                {
                    "session": {
                        "id": sid,
                        "title": session.get("display_title") or meta.get("ai_title"),
                        "cwd": session.get("cwd") or meta.get("cwd"),
                        "status": session.get("status"),
                        "model": session.get("model"),
                        "space_name": session.get("space_name"),
                        "working": working,
                        "active_write": active_write,
                        "transcript_path": str(tpath),
                        "meta": meta,
                    },
                    "total_items": total_items,
                    "shown_range": shown_range,
                    "items": out_items,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    status_tag = " [WORKING]" if working else (" [ACTIVE]" if active_write else "")
    print(f"Session    : {sid}{status_tag}")
    print(f"Title      : {compact_one_line(str(session.get('display_title') or meta.get('ai_title') or ''), 120)}")
    print(f"CWD        : {session.get('cwd') or meta.get('cwd') or '-'}")
    print(f"Model      : {session.get('model') or '-'}  | Status: {session.get('status') or '-'}")
    print(f"Transcript : {tpath}")
    print(f"Items      : showing {shown_range[0]}..{shown_range[1]} of {total_items}")
    print("=" * 72)

    for offset_idx, it in enumerate(sliced, start=shown_range[0] or 1):
        role = it["role"].upper()
        name = f" [{it['name']}]" if it.get("name") else ""
        model_tag = f" ({it['model']})" if it.get("model") and it["role"] == "assistant" else ""
        ts = fmt_ts(it.get("timestamp"))
        body = truncate_text(it["text"], args.max_chars)
        print(f"\n[{offset_idx}] {role}{name}{model_tag} @ {ts}")
        print("-" * 72)
        print(body)
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    root = workbuddy_home()
    rows = load_sessions(root, include_deleted=args.include_deleted)
    rows = filter_sessions(rows, cwd=args.cwd, space=args.space)

    if args.days > 0:
        cutoff = dt.datetime.now().timestamp() - args.days * 86400
        rows = [
            r
            for r in rows
            if to_epoch_seconds(r.get("updated_at") or r.get("created_at")) >= cutoff
        ]

    needle = args.keyword.lower()
    matches: list[dict[str, Any]] = []
    scanned = 0

    for r in rows:
        if scanned >= args.scan_limit:
            break
        tpath_str = str(r.get("transcript_path") or "")
        if not tpath_str:
            continue
        tpath = Path(tpath_str).expanduser()
        if not tpath.is_file():
            continue
        scanned += 1
        try:
            _, items = parse_transcript_messages(tpath, include_tools=False, include_reasoning=False, final_only=False)
        except SystemExit:
            continue

        hits = []
        for idx, it in enumerate(items, start=1):
            text_lower = it["text"].lower()
            pos = text_lower.find(needle)
            if pos != -1:
                start = max(0, pos - 80)
                end = min(len(it["text"]), pos + len(args.keyword) + 120)
                snippet = compact_one_line(it["text"][start:end], 220)
                hits.append({"index": idx, "role": it["role"], "timestamp": it.get("timestamp"), "snippet": snippet})
                if len(hits) >= 3:
                    break

        if hits:
            matches.append(
                {
                    "id": r["id"],
                    "title": compact_one_line(str(r.get("display_title") or ""), 90),
                    "cwd": r.get("cwd"),
                    "model": r.get("model"),
                    "space_name": r.get("space_name"),
                    "updated_at": fmt_ts(r.get("updated_at")),
                    "hits": hits,
                }
            )
            if len(matches) >= args.limit:
                break

    if args.json:
        print(json.dumps({"keyword": args.keyword, "scanned": scanned, "matches": matches}, ensure_ascii=False, indent=2))
        return 0

    if not matches:
        print(f"No message hits for '{args.keyword}' across {scanned} recent WorkBuddy sessions.")
        return 0

    print(f"Found {len(matches)} session(s) matching '{args.keyword}' (scanned {scanned}):\n")
    for idx, m in enumerate(matches, start=1):
        print(f"{idx}. {m['id']}  {m['updated_at']}")
        print(f"   title : {m['title']}")
        print(f"   cwd   : {m['cwd']}  | model: {m.get('model') or '-'}")
        for h in m["hits"]:
            print(f"   hit #{h['index']} ({h['role']}): {h['snippet']}")
    return 0


def read_prompt(prompt_arg: str | None, prompt_file: str | None) -> str:
    if prompt_file:
        return Path(prompt_file).expanduser().read_text(encoding="utf-8")
    if prompt_arg == "-":
        return sys.stdin.read()
    if prompt_arg:
        return prompt_arg
    raise SystemExit("Provide a prompt argument, '-' for stdin, or --prompt-file.")


def apply_mode_flags(cmd: list[str], mode: str, explicit_tools: str | None) -> None:
    if mode == "text-only":
        cmd.extend(["--tools", ""])
    elif mode == "read-only":
        cmd.extend(["--permission-mode", "plan"])
    elif mode == "edit":
        cmd.extend(["--permission-mode", "acceptEdits"])
    elif mode == "full":
        cmd.extend(["--permission-mode", "bypassPermissions", "-y"])

    if explicit_tools is not None:
        cmd.extend(["--tools", explicit_tools])


def parse_cli_json_output(stdout_text: str) -> dict[str, Any]:
    """Parse `codebuddy -p --output-format json` stdout cleanly (handles both JSON list and dict)."""
    stripped = (stdout_text or "").strip()
    if not stripped:
        return {}

    def extract_from_list(arr: list[Any]) -> dict[str, Any]:
        result_obj: dict[str, Any] = {}
        last_assistant_text = ""
        last_model = ""
        session_id = None
        for item in arr:
            if not isinstance(item, dict):
                continue
            if item.get("session_id") or item.get("sessionId"):
                session_id = item.get("session_id") or item.get("sessionId")
            if item.get("type") == "message" and item.get("role") == "assistant":
                txt = extract_content_text(item.get("content"))
                if txt:
                    last_assistant_text = txt
                pd = item.get("providerData")
                if isinstance(pd, dict):
                    last_model = str(pd.get("requestModelId") or pd.get("model") or last_model)
            elif item.get("type") == "result":
                result_obj = dict(item)
        if not result_obj and last_assistant_text:
            result_obj = {"result": last_assistant_text}
        if session_id and not result_obj.get("session_id"):
            result_obj["session_id"] = session_id
        if last_model and not result_obj.get("model"):
            result_obj["model"] = last_model
        return result_obj

    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj
        if isinstance(obj, list):
            return extract_from_list(obj)
    except json.JSONDecodeError:
        pass
    # Fallback: scan JSONL / last JSON object line
    parsed_lines = []
    for line in stripped.splitlines():
        line_s = line.strip()
        if line_s.startswith("{") and line_s.endswith("}"):
            try:
                item = json.loads(line_s)
                if isinstance(item, dict):
                    parsed_lines.append(item)
            except json.JSONDecodeError:
                continue
    if parsed_lines:
        return extract_from_list(parsed_lines)
    return {}


def run_codebuddy_cli(
    root: Path,
    runner: dict[str, Any],
    cli_args: list[str],
    prompt: str,
    dry_run: bool,
    want_json: bool,
    output_file: str | None,
    exec_cwd: str | None = None,
    use_default_config_dir: bool = False,
    internet_env: str = "internal",
) -> int:
    env = os.environ.copy()
    env.update(runner.get("env_extra") or {})
    if not use_default_config_dir and not env.get("CODEBUDDY_CONFIG_DIR"):
        env["CODEBUDDY_CONFIG_DIR"] = str(root)
    if internet_env and internet_env != "auto" and not env.get("CODEBUDDY_INTERNET_ENVIRONMENT"):
        env["CODEBUDDY_INTERNET_ENVIRONMENT"] = internet_env
    env.setdefault("CODEBUDDY_SESSION_HISTORY_CLEANUP", "0")

    full_cmd = runner["cmd_prefix"] + cli_args

    if dry_run:
        payload = {
            "dry_run": True,
            "runner_mode": runner["mode"],
            "config_dir": env.get("CODEBUDDY_CONFIG_DIR", "(default ~/.codebuddy)"),
            "internet_env": env.get("CODEBUDDY_INTERNET_ENVIRONMENT", "(auto)"),
            "exec_cwd": exec_cwd or os.getcwd(),
            "command": full_cmd,
            "prompt_preview": compact_one_line(prompt, 200),
            "auth_env_present": bool(env.get("CODEBUDDY_API_KEY") or env.get("CODEBUDDY_AUTH_TOKEN")),
        }
        if want_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("RUNNER   :", runner["mode"])
            print("CONFIG   :", payload["config_dir"])
            print("ENV      :", payload["internet_env"])
            print("EXEC CWD :", payload["exec_cwd"])
            print("DRY RUN  :", " ".join(full_cmd))
            print("PROMPT   :", compact_one_line(prompt, 200))
        return 0

    proc = subprocess.run(
        full_cmd,
        input=prompt,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        cwd=exec_cwd,
        env=env,
    )

    parsed = parse_cli_json_output(proc.stdout)
    session_id = parsed.get("session_id") or parsed.get("sessionId")
    reply = (
        parsed.get("result")
        or parsed.get("message")
        or parsed.get("text")
        or ("" if parsed else (proc.stdout or "").strip())
    )
    if isinstance(reply, (dict, list)):
        reply = json.dumps(reply, ensure_ascii=False)
    reply_str = str(reply or "").strip()

    if output_file and reply_str:
        out_p = Path(output_file).expanduser()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(reply_str, encoding="utf-8")

    stderr_tail = "\n".join((proc.stderr or "").splitlines()[-15:])
    auth_error = "Authentication required" in (proc.stderr or "") or "Authentication required" in (proc.stdout or "")

    result = {
        "returncode": proc.returncode,
        "runner_mode": runner["mode"],
        "config_dir": env.get("CODEBUDDY_CONFIG_DIR", ""),
        "session_id": session_id,
        "is_error": parsed.get("is_error"),
        "usage": parsed.get("usage"),
        "reply": reply_str,
        "stderr_tail": stderr_tail,
    }
    if auth_error:
        result["auth_hint"] = (
            "CLI is not authenticated for CODEBUDDY_CONFIG_DIR="
            + env.get("CODEBUDDY_CONFIG_DIR", str(root))
            + ". Either set CODEBUDDY_API_KEY (and CODEBUDDY_INTERNET_ENVIRONMENT=internal for CN), "
            "or install `@tencent-ai/codebuddy-code` and run `/login` with CODEBUDDY_CONFIG_DIR set to this folder."
        )

    if want_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if session_id:
            print(f"Session ID : {session_id}")
        if parsed.get("usage"):
            print(f"Usage      : {json.dumps(parsed['usage'], ensure_ascii=False)}")
        if reply_str:
            print("\n--- WorkBuddy / CodeBuddy Reply ---")
            print(reply_str)
        if proc.returncode != 0:
            print(f"\nCLI exited with code {proc.returncode}", file=sys.stderr)
            if stderr_tail:
                print(stderr_tail, file=sys.stderr)
            if auth_error:
                print(f"\nHint: {result['auth_hint']}", file=sys.stderr)
    return proc.returncode


def cmd_login(args: argparse.Namespace) -> int:
    root = workbuddy_home()
    runner = resolve_cli_runner(root)
    if runner["mode"] == "bundled-lite-wb":
        raise SystemExit(
            "Interactive `/login` requires standalone `@tencent-ai/codebuddy-code` CLI "
            "(bundled WorkBuddy lite-wb has no TUI).\n"
            "Install it with: npm.cmd install -g @tencent-ai/codebuddy-code"
        )
    env = os.environ.copy()
    env.update(runner.get("env_extra") or {})
    if not args.use_codebuddy_home:
        env["CODEBUDDY_CONFIG_DIR"] = str(root)
    if args.env and args.env != "auto":
        env["CODEBUDDY_INTERNET_ENVIRONMENT"] = args.env
    env.setdefault("CODEBUDDY_SESSION_HISTORY_CLEANUP", "0")

    print(f"Launching interactive CodeBuddy CLI ({runner['display_path']})...")
    print(f"  CODEBUDDY_CONFIG_DIR           = {env.get('CODEBUDDY_CONFIG_DIR', '(default ~/.codebuddy)')}")
    print(f"  CODEBUDDY_INTERNET_ENVIRONMENT = {env.get('CODEBUDDY_INTERNET_ENVIRONMENT', '(auto)')}")
    print("Complete QR / browser login (or type /login), then type /exit when done.\n")
    proc = subprocess.run(runner["cmd_prefix"], env=env)
    return proc.returncode


def cmd_send(args: argparse.Namespace) -> int:
    root = workbuddy_home()
    runner = resolve_cli_runner(root)

    target = args.target
    prompt_arg = args.prompt_opt or args.prompt
    if args.last and prompt_arg is None and target is not None:
        prompt_arg = target
        target = None

    prompt = read_prompt(prompt_arg, args.prompt_file)
    session = resolve_session(root, target, use_last=args.last, cwd=args.cwd, space=args.space)
    sid = str(session.get("id") or "")
    if not sid:
        raise SystemExit("Resolved session has no valid ID.")

    tpath_str = str(session.get("transcript_path") or "")
    tpath = Path(tpath_str).expanduser() if tpath_str else None
    working = bool(session.get("working"))
    active_write = is_transcript_actively_writing(tpath)

    if not args.force and not args.fork:
        if working:
            raise SystemExit(
                f"Refusing to send: session {sid} has status='{session.get('status')}' in WorkBuddy Desktop. "
                "Wait until it completes, pass --fork to branch safely, or pass --force."
            )
        if active_write:
            raise SystemExit(
                f"Refusing to send: session {sid} transcript was just updated and appears actively running. "
                "Wait a few seconds, pass --fork, or pass --force."
            )

    cli_args = ["-p", "--output-format", "json", "-r", sid]
    if args.fork:
        cli_args.append("--fork-session")
    apply_mode_flags(cli_args, args.mode, args.tools)
    if args.model:
        cli_args.extend(["--model", args.model])
    if args.effort:
        cli_args.extend(["--effort", args.effort])
    if args.max_turns:
        cli_args.extend(["--max-turns", str(args.max_turns)])
    for extra_dir in args.add_dir or []:
        cli_args.extend(["--add-dir", str(Path(extra_dir).expanduser())])

    exec_cwd = None
    session_cwd = str(session.get("cwd") or "").strip()
    if args.exec_cwd:
        exec_cwd = str(Path(args.exec_cwd).expanduser())
    elif session_cwd and Path(session_cwd).is_dir():
        exec_cwd = session_cwd

    return run_codebuddy_cli(
        root,
        runner,
        cli_args,
        prompt,
        dry_run=args.dry_run,
        want_json=args.json,
        output_file=args.output_file,
        exec_cwd=exec_cwd,
        use_default_config_dir=args.use_codebuddy_home,
        internet_env=args.env,
    )


def cmd_start(args: argparse.Namespace) -> int:
    root = workbuddy_home()
    runner = resolve_cli_runner(root)
    prompt = read_prompt(args.prompt, args.prompt_file)

    cli_args = ["-p", "--output-format", "json"]
    apply_mode_flags(cli_args, args.mode, args.tools)
    if args.model:
        cli_args.extend(["--model", args.model])
    if args.effort:
        cli_args.extend(["--effort", args.effort])
    if args.max_turns:
        cli_args.extend(["--max-turns", str(args.max_turns)])
    if args.ephemeral:
        cli_args.append("--no-session-persistence")
    for extra_dir in args.add_dir or []:
        cli_args.extend(["--add-dir", str(Path(extra_dir).expanduser())])

    exec_cwd = str(Path(args.cwd).expanduser()) if args.cwd else None

    return run_codebuddy_cli(
        root,
        runner,
        cli_args,
        prompt,
        dry_run=args.dry_run,
        want_json=args.json,
        output_file=args.output_file,
        exec_cwd=exec_cwd,
        use_default_config_dir=args.use_codebuddy_home,
        internet_env=args.env,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bridge to read and drive local WorkBuddy / CodeBuddy sessions.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_doc = sub.add_parser("doctor", help="Inspect WorkBuddy data dir, CLI runner, and auth readiness.")
    p_doc.add_argument("--json", action="store_true", help="Output JSON.")
    p_doc.set_defaults(func=cmd_doctor)

    p_login = sub.add_parser("login", help="Launch interactive CodeBuddy CLI configured for WorkBuddy home to perform /login.")
    p_login.add_argument("--env", choices=["internal", "external", "auto"], default="internal", help="Account region (default: internal for CN).")
    p_login.add_argument("--use-codebuddy-home", action="store_true", help="Store login in ~/.codebuddy instead of ~/.workbuddy.")
    p_login.set_defaults(func=cmd_login)

    p_list = sub.add_parser("list", help="List recent WorkBuddy sessions.")
    p_list.add_argument("--cwd", help="Filter by working directory substring.")
    p_list.add_argument("--space", help="Filter by WorkBuddy space/group/project substring.")
    p_list.add_argument("--status", help="Filter by exact session status (e.g. completed, working, error).")
    p_list.add_argument("--query", "-q", help="Filter by title/cwd/space/model substring.")
    p_list.add_argument("--limit", "-n", type=int, default=20, help="Max rows to show (default: 20, 0=all).")
    p_list.add_argument("--include-deleted", action="store_true", help="Include soft-deleted sessions.")
    p_list.add_argument("--json", action="store_true", help="Output JSON.")
    p_list.set_defaults(func=cmd_list)

    p_read = sub.add_parser("read", help="Read cleaned messages from a WorkBuddy session.")
    p_read.add_argument("target", nargs="?", help="Session UUID, UUID prefix, or title query.")
    p_read.add_argument("--last", action="store_true", help="Read the most recent active session.")
    p_read.add_argument("--cwd", help="Disambiguate --last or query by cwd substring.")
    p_read.add_argument("--space", help="Disambiguate --last or query by space substring.")
    p_read.add_argument("--last-turns", type=int, default=20, help="Show last N items (default: 20, 0=all).")
    p_read.add_argument("--offset", type=int, default=0, help="0-based item offset for pagination.")
    p_read.add_argument("--limit", type=int, default=0, help="Number of items to show with --offset.")
    p_read.add_argument("--max-chars", type=int, default=4000, help="Truncate individual items to N chars (0=no limit).")
    p_read.add_argument("--include-tools", action="store_true", help="Include tool calls and results.")
    p_read.add_argument("--include-reasoning", action="store_true", help="Include model reasoning blocks.")
    p_read.add_argument("--final-only", action="store_true", help="Only keep user messages and final assistant reply per turn.")
    p_read.add_argument("--include-boilerplate", action="store_true", help="Keep injected <system-reminder> blocks in user messages.")
    p_read.add_argument("--json", action="store_true", help="Output JSON.")
    p_read.set_defaults(func=cmd_read)

    p_search = sub.add_parser("search", help="Search message text across recent WorkBuddy sessions.")
    p_search.add_argument("keyword", help="Case-insensitive substring to search.")
    p_search.add_argument("--cwd", help="Filter by working directory substring.")
    p_search.add_argument("--space", help="Filter by space/group substring.")
    p_search.add_argument("--days", type=int, default=30, help="Only scan sessions updated within N days (default: 30, 0=all).")
    p_search.add_argument("--scan-limit", type=int, default=80, help="Max sessions to scan (default: 80).")
    p_search.add_argument("--limit", "-n", type=int, default=10, help="Max matched sessions to return (default: 10).")
    p_search.add_argument("--include-deleted", action="store_true", help="Include deleted sessions.")
    p_search.add_argument("--json", action="store_true", help="Output JSON.")
    p_search.set_defaults(func=cmd_search)

    p_send = sub.add_parser("send", help="Resume and send a prompt to an existing WorkBuddy session via `codebuddy -p -r`.")
    p_send.add_argument("target", nargs="?", help="Session UUID, UUID prefix, or title.")
    p_send.add_argument("prompt", nargs="?", help="Prompt text (or '-' to read from stdin).")
    p_send.add_argument("-p", "--prompt", dest="prompt_opt", help="Explicit prompt text (handy with --last).")
    p_send.add_argument("--last", action="store_true", help="Target the most recent active session.")
    p_send.add_argument("--cwd", help="Disambiguate --last or target by cwd substring.")
    p_send.add_argument("--space", help="Disambiguate --last or target by space substring.")
    p_send.add_argument("--exec-cwd", help="Override subprocess working directory (defaults to session cwd if it exists).")
    p_send.add_argument("--prompt-file", help="Read prompt from a file instead of CLI argument.")
    p_send.add_argument(
        "--mode",
        choices=["text-only", "read-only", "edit", "full"],
        default="read-only",
        help="Execution safety preset (default: read-only -> --permission-mode plan).",
    )
    p_send.add_argument("--tools", help='Override built-in tools list (e.g. "" or "Read,Glob,Grep").')
    p_send.add_argument("-m", "--model", help="Override model ID.")
    p_send.add_argument("--effort", choices=["minimal", "low", "medium", "high", "xhigh", "max"], help="Reasoning effort level.")
    p_send.add_argument("--max-turns", type=int, help="Limit maximum agentic turns.")
    p_send.add_argument("--add-dir", action="append", help="Additional directory to grant tool access to.")
    p_send.add_argument("--fork", action="store_true", help="Pass --fork-session to branch without mutating the original session.")
    p_send.add_argument("--force", action="store_true", help="Send even if session appears busy.")
    p_send.add_argument("--use-codebuddy-home", action="store_true", help="Do not set CODEBUDDY_CONFIG_DIR to ~/.workbuddy.")
    p_send.add_argument("--env", choices=["internal", "external", "auto"], default="internal", help="Account region (default: internal for CN).")
    p_send.add_argument("-o", "--output-file", help="Save final reply text to file.")
    p_send.add_argument("--dry-run", action="store_true", help="Print command without invoking CLI.")
    p_send.add_argument("--json", action="store_true", help="Output JSON.")
    p_send.set_defaults(func=cmd_send)

    p_start = sub.add_parser("start", help="Start a new non-interactive session via `codebuddy -p`.")
    p_start.add_argument("prompt", nargs="?", help="Prompt text (or '-' to read from stdin).")
    p_start.add_argument("--prompt-file", help="Read prompt from a file.")
    p_start.add_argument("-C", "--cwd", help="Working directory for the new session.")
    p_start.add_argument(
        "--mode",
        choices=["text-only", "read-only", "edit", "full"],
        default="read-only",
        help="Execution safety preset (default: read-only -> --permission-mode plan).",
    )
    p_start.add_argument("--tools", help='Override built-in tools list (e.g. "" or "Read,Glob,Grep").')
    p_start.add_argument("-m", "--model", help="Override model ID.")
    p_start.add_argument("--effort", choices=["minimal", "low", "medium", "high", "xhigh", "max"], help="Reasoning effort level.")
    p_start.add_argument("--max-turns", type=int, help="Limit maximum agentic turns.")
    p_start.add_argument("--add-dir", action="append", help="Additional directory to grant tool access to.")
    p_start.add_argument("--ephemeral", action="store_true", help="Do not persist session files to disk.")
    p_start.add_argument("--use-codebuddy-home", action="store_true", help="Do not set CODEBUDDY_CONFIG_DIR to ~/.workbuddy.")
    p_start.add_argument("--env", choices=["internal", "external", "auto"], default="internal", help="Account region (default: internal for CN).")
    p_start.add_argument("-o", "--output-file", help="Save final reply text to file.")
    p_start.add_argument("--dry-run", action="store_true", help="Print command without invoking CLI.")
    p_start.add_argument("--json", action="store_true", help="Output JSON.")
    p_start.set_defaults(func=cmd_start)

    return parser


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
