#!/usr/bin/env python3
"""
codex_bridge.py - Read local Codex CLI/App sessions and drive Codex sessions via CLI.

Zero external dependencies (Python 3 standard library only).
Respects $CODEX_HOME (defaults to ~/.codex).
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import glob
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


BOILERPLATE_PREFIXES = (
    "<environment_context>",
    "<permissions instructions>",
    "<collaboration_mode>",
    "<INSTRUCTIONS>",
    "# AGENTS.md instructions",
    "<app-context>",
    "<skill>",
    "<user_instructions>",
)


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


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


def find_latest_state_db(root: Path) -> Path | None:
    candidates = sorted(root.glob("state_*.sqlite"))
    if not candidates:
        return None

    def version_key(path: Path) -> tuple[int, str]:
        m = re.search(r"state_(\d+)\.sqlite$", path.name)
        return (int(m.group(1)) if m else -1, path.name)

    candidates.sort(key=version_key, reverse=True)
    return candidates[0]


def is_writer_locked(root: Path, session_id: str) -> bool:
    """Check whether another Codex process currently holds the advisory writer lock."""
    lock_path = root / "thread-writer-locks" / f"{session_id}.lock"
    if not lock_path.exists():
        return False
    fd = None
    try:
        fd = os.open(str(lock_path), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except BlockingIOError:
            return True
    except OSError:
        return False
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def is_turn_running(rollout_path: Path | None) -> bool:
    """Heuristically check rollout tail to see if a turn started without completing."""
    if not rollout_path or not rollout_path.is_file():
        return False
    try:
        size = rollout_path.stat().st_size
        read_size = min(size, 65536)
        with rollout_path.open("rb") as f:
            if size > read_size:
                f.seek(size - read_size)
            chunk = f.read(read_size).decode("utf-8", errors="replace")
    except OSError:
        return False

    last_task_event = None
    for line in chunk.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "event_msg" and isinstance(obj.get("payload"), dict):
            pt = obj["payload"].get("type")
            if pt in ("task_started", "task_complete", "turn_aborted", "turn_failed"):
                last_task_event = pt
    return last_task_event == "task_started"


def load_session_index_names(root: Path) -> dict[str, str]:
    idx_path = root / "session_index.jsonl"
    names: dict[str, str] = {}
    if not idx_path.is_file():
        return names
    try:
        with idx_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sid = obj.get("id")
                tname = obj.get("thread_name")
                if sid and tname:
                    names[str(sid)] = str(tname)
    except OSError:
        pass
    return names


def list_sessions_from_db(
    root: Path,
    include_archived: bool = False,
    include_subagents: bool = False,
) -> list[dict[str, Any]] | None:
    db_path = find_latest_state_db(root)
    if db_path is None:
        return None
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
    except sqlite3.Error:
        return None

    try:
        cols = {row["name"] for row in con.execute("PRAGMA table_info(threads)")}
        if not cols:
            return None

        wanted = [
            "id",
            "rollout_path",
            "created_at",
            "updated_at",
            "recency_at",
            "cwd",
            "title",
            "name",
            "preview",
            "first_user_message",
            "archived",
            "is_pinned",
            "git_branch",
            "model",
            "source",
            "thread_source",
            "originator",
            "tokens_used",
            "agent_nickname",
            "agent_role",
            "attached_thread_parent_id",
        ]
        select_cols = [c for c in wanted if c in cols]
        order_col = "recency_at" if "recency_at" in cols else "updated_at"
        where_clauses = []
        if not include_archived and "archived" in cols:
            where_clauses.append("archived = 0")
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"SELECT {', '.join(select_cols)} FROM threads {where_sql} ORDER BY {order_col} DESC, updated_at DESC"

        index_names = load_session_index_names(root)
        rows: list[dict[str, Any]] = []
        for row in con.execute(sql):
            item = dict(row)
            sid = str(item.get("id") or "")
            is_subagent = bool(
                item.get("attached_thread_parent_id")
                or item.get("agent_role")
                or str(item.get("source") or "").startswith("subagent")
                or str(item.get("thread_source") or "").startswith("subagent")
            )
            if not include_subagents and is_subagent:
                continue
            item["is_subagent"] = is_subagent
            item["thread_name"] = item.get("name") or index_names.get(sid) or ""
            item["display_title"] = (
                item["thread_name"]
                or item.get("title")
                or item.get("preview")
                or item.get("first_user_message")
                or "(untitled)"
            )
            item["locked"] = is_writer_locked(root, sid)
            rp = item.get("rollout_path")
            item["running"] = is_turn_running(Path(str(rp)).expanduser()) if (item["locked"] and rp) else False
            rows.append(item)
        return rows
    except sqlite3.Error:
        return None
    finally:
        con.close()


def scan_sessions_from_files(root: Path, include_archived: bool = False) -> list[dict[str, Any]]:
    index_names = load_session_index_names(root)
    patterns = [str(root / "sessions" / "**" / "*.jsonl")]
    if include_archived:
        patterns.append(str(root / "archived_sessions" / "**" / "*.jsonl"))

    files: list[Path] = []
    for pat in patterns:
        files.extend(Path(p) for p in glob.glob(pat, recursive=True))

    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    rows: list[dict[str, Any]] = []
    for path in files:
        meta: dict[str, Any] = {}
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for _ in range(20):
                    line = f.readline()
                    if not line:
                        break
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if obj.get("type") == "session_meta" and isinstance(obj.get("payload"), dict):
                        meta = obj["payload"]
                        break
        except OSError:
            continue

        sid = str(meta.get("id") or meta.get("session_id") or path.stem)
        stat = path.stat()
        tname = index_names.get(sid, "")
        rows.append(
            {
                "id": sid,
                "rollout_path": str(path),
                "created_at": meta.get("timestamp") or int(stat.st_ctime),
                "updated_at": int(stat.st_mtime),
                "recency_at": int(stat.st_mtime),
                "cwd": meta.get("cwd") or "",
                "title": tname or path.name,
                "name": tname,
                "thread_name": tname,
                "display_title": tname or path.name,
                "archived": 1 if "archived_sessions" in path.parts else 0,
                "git_branch": (meta.get("git") or {}).get("branch") if isinstance(meta.get("git"), dict) else None,
                "model": None,
                "source": meta.get("source"),
                "originator": meta.get("originator"),
                "is_subagent": bool(meta.get("parent_thread_id")),
                "locked": is_writer_locked(root, sid),
                "running": is_turn_running(path),
            }
        )
    return rows


def load_sessions(
    root: Path,
    include_archived: bool = False,
    include_subagents: bool = False,
) -> list[dict[str, Any]]:
    rows = list_sessions_from_db(root, include_archived=include_archived, include_subagents=include_subagents)
    if rows is not None:
        return rows
    rows = scan_sessions_from_files(root, include_archived=include_archived)
    if not include_subagents:
        rows = [r for r in rows if not r.get("is_subagent")]
    return rows


def filter_sessions(
    rows: list[dict[str, Any]],
    cwd: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    result = rows
    if cwd:
        needle = cwd.lower()
        result = [r for r in result if needle in str(r.get("cwd") or "").lower()]
    if query:
        needle = query.lower()
        filtered = []
        for r in result:
            haystack = " ".join(
                str(r.get(k) or "")
                for k in ("id", "title", "name", "thread_name", "display_title", "preview", "first_user_message", "cwd", "git_branch")
            ).lower()
            if needle in haystack:
                filtered.append(r)
        result = filtered
    return result


def resolve_session(root: Path, target: str | None, use_last: bool = False, cwd: str | None = None) -> dict[str, Any]:
    rows = load_sessions(root, include_archived=True, include_subagents=True)
    if use_last:
        candidates = [r for r in rows if not r.get("archived") and not r.get("is_subagent")]
        if cwd:
            candidates = filter_sessions(candidates, cwd=cwd)
        if not candidates:
            raise SystemExit("No matching active Codex session found.")
        return candidates[0]

    if not target:
        raise SystemExit("Specify a session id/prefix/name or pass --last.")

    target_lower = target.lower()
    # 1. Exact ID match
    for r in rows:
        if str(r.get("id", "")).lower() == target_lower:
            return r
    # 2. Exact thread name match
    exact_names = [r for r in rows if str(r.get("thread_name") or r.get("name") or "").lower() == target_lower]
    if len(exact_names) == 1:
        return exact_names[0]
    # 3. ID prefix match
    prefix_matches = [r for r in rows if str(r.get("id", "")).lower().startswith(target_lower)]
    if len(prefix_matches) == 1:
        return prefix_matches[0]
    if len(prefix_matches) > 1:
        ids = ", ".join(str(r["id"]) for r in prefix_matches[:5])
        raise SystemExit(f"Ambiguous session prefix '{target}'. Matches: {ids}")
    # 4. Title / name substring match (most recent wins only if unambiguous)
    sub_matches = filter_sessions(rows, cwd=cwd, query=target)
    if len(sub_matches) == 1:
        return sub_matches[0]
    if len(sub_matches) > 1:
        preview = "\n".join(
            f"  - {r['id']}  [{fmt_ts(r.get('recency_at') or r.get('updated_at'))}]  {compact_one_line(str(r.get('display_title', '')), 70)}"
            for r in sub_matches[:8]
        )
        raise SystemExit(f"Multiple sessions matched '{target}'. Please specify an exact session ID:\n{preview}")

    # 5. Direct path fallback
    maybe_path = Path(target).expanduser()
    if maybe_path.is_file():
        return {"id": maybe_path.stem, "rollout_path": str(maybe_path), "display_title": maybe_path.name}

    raise SystemExit(f"Session not found: {target}")


def compact_one_line(text: str, max_len: int = 80) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if max_len > 0 and len(cleaned) > max_len:
        return cleaned[: max_len - 1] + "…"
    return cleaned


def is_boilerplate_text(text: str) -> bool:
    stripped = text.lstrip()
    return any(stripped.startswith(prefix) for prefix in BOILERPLATE_PREFIXES)


def extract_message_text(payload: dict[str, Any], include_boilerplate: bool = False) -> str:
    content = payload.get("content")
    if isinstance(content, str):
        return "" if (not include_boilerplate and is_boilerplate_text(content)) else content.strip()
    if not isinstance(content, list):
        return ""

    meta_passthrough = payload.get("internal_chat_message_metadata_passthrough")
    kinds = meta_passthrough.get("content_item_kinds") if isinstance(meta_passthrough, dict) else None

    parts: list[str] = []
    for idx, block in enumerate(content):
        if isinstance(block, str):
            text = block
            btype = "text"
        elif isinstance(block, dict):
            btype = str(block.get("type") or "")
            if btype in ("input_text", "output_text", "text"):
                text = str(block.get("text") or "")
            elif btype in ("input_image", "image_url", "image"):
                parts.append("[image]")
                continue
            else:
                text = str(block.get("text") or "")
        else:
            continue

        if not text.strip():
            continue

        kind = kinds[idx] if isinstance(kinds, list) and idx < len(kinds) else None
        if not include_boilerplate:
            if kind and str(kind) not in ("user_message", "text", "assistant_message", "final_answer", "commentary"):
                if is_boilerplate_text(text):
                    continue
            if is_boilerplate_text(text):
                continue

        parts.append(text.strip())

    return "\n\n".join(parts).strip()


def truncate_text(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated, total {len(text)} chars]"


def parse_rollout_messages(
    rollout_path: Path,
    include_tools: bool = False,
    final_only: bool = False,
    include_boilerplate: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    meta: dict[str, Any] = {}
    items: list[dict[str, Any]] = []

    if not rollout_path.is_file():
        raise SystemExit(f"Rollout file does not exist: {rollout_path}")

    with rollout_path.open("r", encoding="utf-8", errors="replace") as f:
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
            payload = obj.get("payload")
            if not isinstance(payload, dict):
                continue

            if etype == "session_meta" and not meta:
                meta = {
                    "id": payload.get("id") or payload.get("session_id"),
                    "timestamp": payload.get("timestamp") or ts,
                    "cwd": payload.get("cwd"),
                    "cli_version": payload.get("cli_version"),
                    "originator": payload.get("originator"),
                    "source": payload.get("source"),
                    "git": payload.get("git"),
                }
                continue

            if etype != "response_item":
                continue

            ptype = payload.get("type")
            if ptype == "message":
                role = payload.get("role")
                if role not in ("user", "assistant"):
                    continue
                phase = payload.get("phase")
                if role == "assistant" and final_only and phase and phase != "final_answer":
                    continue
                text = extract_message_text(payload, include_boilerplate=include_boilerplate)
                if not text:
                    continue
                items.append(
                    {
                        "kind": "message",
                        "role": role,
                        "phase": phase,
                        "timestamp": ts,
                        "line": line_no,
                        "text": text,
                    }
                )
            elif include_tools and ptype in ("function_call", "custom_tool_call"):
                name = payload.get("name") or ptype
                raw_args = payload.get("arguments") if ptype == "function_call" else payload.get("input")
                items.append(
                    {
                        "kind": "tool_call",
                        "role": "tool_call",
                        "name": name,
                        "call_id": payload.get("call_id"),
                        "timestamp": ts,
                        "line": line_no,
                        "text": str(raw_args or ""),
                    }
                )
            elif include_tools and ptype in ("function_call_output", "custom_tool_call_output"):
                out = payload.get("output")
                if isinstance(out, list):
                    out_text = json.dumps(out, ensure_ascii=False)
                else:
                    out_text = str(out or "")
                items.append(
                    {
                        "kind": "tool_output",
                        "role": "tool_output",
                        "name": payload.get("name") or "",
                        "call_id": payload.get("call_id"),
                        "timestamp": ts,
                        "line": line_no,
                        "text": out_text,
                    }
                )

    return meta, items


def cmd_list(args: argparse.Namespace) -> int:
    root = codex_home()
    rows = load_sessions(root, include_archived=args.include_archived, include_subagents=args.include_subagents)
    rows = filter_sessions(rows, cwd=args.cwd, query=args.query)
    total = len(rows)
    rows = rows[: args.limit] if args.limit > 0 else rows

    if args.json:
        print(json.dumps({"total": total, "sessions": rows}, ensure_ascii=False, indent=2))
        return 0

    if not rows:
        print("No matching Codex sessions found.")
        return 0

    print(f"Showing {len(rows)} of {total} Codex sessions (CODEX_HOME={root}):\n")
    for idx, r in enumerate(rows, start=1):
        ts = fmt_ts(r.get("recency_at") or r.get("updated_at") or r.get("created_at"))
        flags = []
        if r.get("running"):
            flags.append("RUNNING")
        elif r.get("locked"):
            flags.append("LOCKED")
        if r.get("archived"):
            flags.append("ARCHIVED")
        if r.get("is_pinned"):
            flags.append("PINNED")
        if r.get("is_subagent"):
            flags.append(f"SUBAGENT:{r.get('agent_role') or 'child'}")
        flag_str = f" [{' '.join(flags)}]" if flags else ""
        title = compact_one_line(str(r.get("display_title") or ""), 90)
        cwd = str(r.get("cwd") or "-")
        branch = r.get("git_branch")
        branch_str = f" ({branch})" if branch else ""
        model = r.get("model") or "-"
        print(f"{idx:2d}. {r['id']}  {ts}{flag_str}")
        print(f"    title : {title}")
        print(f"    cwd   : {cwd}{branch_str}  | model: {model}")
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    root = codex_home()
    session = resolve_session(root, args.target, use_last=args.last, cwd=args.cwd)
    rollout = Path(str(session.get("rollout_path") or "")).expanduser()
    meta, items = parse_rollout_messages(
        rollout,
        include_tools=args.include_tools,
        final_only=args.final_only,
        include_boilerplate=args.include_boilerplate,
    )

    total_items = len(items)
    if args.offset > 0 or args.limit > 0:
        start = max(0, args.offset)
        end = start + args.limit if args.limit > 0 else total_items
        sliced = items[start:end]
        shown_range = (start + 1, min(end, total_items))
    elif args.last_turns > 0 and total_items > args.last_turns:
        sliced = items[-args.last_turns :]
        shown_range = (total_items - len(sliced) + 1, total_items)
    else:
        sliced = items
        shown_range = (1, total_items) if total_items else (0, 0)

    sid = str(session.get("id") or meta.get("id") or "")
    locked = is_writer_locked(root, sid)
    running = is_turn_running(rollout) if locked else False

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
                        "title": session.get("display_title"),
                        "cwd": session.get("cwd") or meta.get("cwd"),
                        "locked": locked,
                        "running": running,
                        "rollout_path": str(rollout),
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

    status_tag = " [RUNNING]" if running else (" [LOCKED - loaded in Codex App/TUI]" if locked else "")
    print(f"Session : {sid}{status_tag}")
    print(f"Title   : {compact_one_line(str(session.get('display_title') or ''), 120)}")
    print(f"CWD     : {session.get('cwd') or meta.get('cwd') or '-'}")
    print(f"Rollout : {rollout}")
    print(f"Items   : showing {shown_range[0]}..{shown_range[1]} of {total_items}")
    print("=" * 72)

    for offset_idx, it in enumerate(sliced, start=shown_range[0]):
        role = it["role"].upper()
        phase = f" ({it['phase']})" if it.get("phase") else ""
        name = f" [{it['name']}]" if it.get("name") else ""
        ts = fmt_ts(it.get("timestamp"))
        body = truncate_text(it["text"], args.max_chars)
        print(f"\n[{offset_idx}] {role}{phase}{name} @ {ts}")
        print("-" * 72)
        print(body)
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    root = codex_home()
    rows = load_sessions(root, include_archived=args.include_archived, include_subagents=args.include_subagents)
    rows = filter_sessions(rows, cwd=args.cwd)

    if args.days > 0:
        cutoff = (dt.datetime.now().timestamp()) - args.days * 86400
        filtered = []
        for r in rows:
            ts = r.get("recency_at") or r.get("updated_at") or 0
            try:
                ts_f = float(ts)
                if ts_f > 1e12:
                    ts_f /= 1000.0
                if ts_f >= cutoff:
                    filtered.append(r)
            except Exception:
                filtered.append(r)
        rows = filtered

    needle = args.keyword.lower()
    matches: list[dict[str, Any]] = []
    scanned = 0

    for r in rows:
        if scanned >= args.scan_limit:
            break
        rollout_str = r.get("rollout_path")
        if not rollout_str:
            continue
        rollout = Path(str(rollout_str)).expanduser()
        if not rollout.is_file():
            continue
        scanned += 1
        try:
            _, items = parse_rollout_messages(rollout, include_tools=False, final_only=False)
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
                    "updated_at": fmt_ts(r.get("recency_at") or r.get("updated_at")),
                    "hits": hits,
                }
            )
            if len(matches) >= args.limit:
                break

    if args.json:
        print(json.dumps({"keyword": args.keyword, "scanned": scanned, "matches": matches}, ensure_ascii=False, indent=2))
        return 0

    if not matches:
        print(f"No message hits for '{args.keyword}' across {scanned} recent sessions.")
        return 0

    print(f"Found {len(matches)} session(s) matching '{args.keyword}' (scanned {scanned}):\n")
    for idx, m in enumerate(matches, start=1):
        print(f"{idx}. {m['id']}  {m['updated_at']}")
        print(f"   title : {m['title']}")
        print(f"   cwd   : {m['cwd']}")
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


def parse_codex_version(binary: str) -> tuple[int, int, int, int, int]:
    """Return comparable version tuple for a codex CLI binary (higher is newer)."""
    try:
        proc = subprocess.run([binary, "--version"], text=True, capture_output=True, timeout=5)
        text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    except Exception:
        return (0, 0, 0, 0, 0)
    m = re.search(r"(\d+)\.(\d+)\.(\d+)(?:-(?:alpha|beta|rc)\.?(\d+))?", text)
    if not m:
        return (0, 0, 0, 0, 0)
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    # Stable release (no pre-release suffix) ranks above pre-release of same x.y.z
    if m.group(4) is None:
        return (major, minor, patch, 1, 0)
    return (major, minor, patch, 0, int(m.group(4)))


def ensure_codex_binary() -> str:
    override = os.environ.get("CODEX_BRIDGE_BIN")
    if override:
        p = Path(override).expanduser()
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
        raise SystemExit(f"CODEX_BRIDGE_BIN is not an executable file: {override}")

    candidates: list[str] = []
    for fixed in (
        "/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex",
        "/Applications/Codex.app/Contents/Resources/codex",
        "/Applications/Codex.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex",
    ):
        if Path(fixed).is_file() and os.access(fixed, os.X_OK):
            candidates.append(fixed)

    which_bin = shutil.which("codex")
    if which_bin and which_bin not in candidates:
        candidates.append(which_bin)

    if not candidates:
        raise SystemExit("`codex` binary not found in PATH or known macOS app bundles.")

    if len(candidates) == 1:
        return candidates[0]

    candidates.sort(key=parse_codex_version, reverse=True)
    return candidates[0]


def resolve_default_model(root: Path) -> str | None:
    """Resolve the newest default visible model from Codex's local models_cache."""
    for fname in ("models_cache.json", "models_cache.codex_work_desktop.json"):
        cache_path = root / fname
        if not cache_path.is_file():
            continue
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            continue
        visible = [
            m
            for m in models
            if isinstance(m, dict) and m.get("slug") and m.get("visibility") == "list"
        ]
        if visible:
            visible.sort(key=lambda m: (m.get("priority") if isinstance(m.get("priority"), (int, float)) else 999999))
            return str(visible[0]["slug"])

    cfg_path = root / "config.toml"
    if cfg_path.is_file():
        try:
            for line in cfg_path.read_text(encoding="utf-8", errors="replace").splitlines():
                m = re.match(r'^\s*model\s*=\s*["\']([^"\']+)["\']', line)
                if m:
                    return m.group(1)
        except OSError:
            pass
    return None


def run_codex_exec(
    cmd: list[str],
    prompt: str,
    dry_run: bool,
    want_json: bool,
    output_file: str | None,
    exec_cwd: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> int:
    if dry_run:
        payload = {
            "dry_run": True,
            "exec_cwd": exec_cwd,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "command": cmd,
            "prompt_preview": compact_one_line(prompt, 200),
        }
        if want_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            if exec_cwd:
                print("EXEC CWD :", exec_cwd)
            if model:
                print("MODEL    :", model)
            if reasoning_effort:
                print("REASONING:", reasoning_effort)
            print("DRY RUN  :", " ".join(cmd))
            print("PROMPT   :", compact_one_line(prompt, 200))
        return 0

    temp_out: Path | None = None
    final_out_path: Path
    if output_file:
        final_out_path = Path(output_file).expanduser()
        final_out_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        fd, name = tempfile.mkstemp(prefix="codex-bridge-last-", suffix=".txt")
        os.close(fd)
        temp_out = Path(name)
        final_out_path = temp_out

    full_cmd = cmd + ["-o", str(final_out_path), "-"]
    try:
        proc = subprocess.run(
            full_cmd,
            input=prompt,
            text=True,
            capture_output=True,
            cwd=exec_cwd,
        )
        events: list[dict[str, Any]] = []
        thread_id = None
        usage = None
        errors: list[str] = []

        for line in proc.stdout.splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            try:
                ev = json.loads(line_s)
            except json.JSONDecodeError:
                continue
            events.append(ev)
            ev_type = ev.get("type")
            if ev_type == "thread.started" and ev.get("thread_id"):
                thread_id = ev["thread_id"]
            elif ev_type == "turn.completed" and ev.get("usage"):
                usage = ev["usage"]
            elif ev_type in ("error", "turn.failed"):
                errors.append(json.dumps(ev, ensure_ascii=False))

        last_message = ""
        if final_out_path.is_file():
            last_message = final_out_path.read_text(encoding="utf-8", errors="replace").strip()

        result = {
            "returncode": proc.returncode,
            "thread_id": thread_id,
            "model": model,
            "reasoning_effort": reasoning_effort,
            "usage": usage,
            "last_message": last_message,
            "errors": errors,
            "stderr_tail": "\n".join(proc.stderr.splitlines()[-15:]) if proc.stderr else "",
        }

        if want_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            if thread_id:
                print(f"Thread ID : {thread_id}")
            if model or reasoning_effort:
                print(f"Model     : {model or '(cli-default)'}  | reasoning: {reasoning_effort or '(cli-default)'}")
            if usage:
                print(f"Usage     : {json.dumps(usage, ensure_ascii=False)}")
            if last_message:
                print("\n--- Codex Reply ---")
                print(last_message)
            elif proc.stdout.strip():
                print("\n--- Raw Output ---")
                print(proc.stdout.strip())
            if proc.returncode != 0:
                print(f"\nCodex exited with code {proc.returncode}", file=sys.stderr)
                if result["stderr_tail"]:
                    print(result["stderr_tail"], file=sys.stderr)
        return proc.returncode
    finally:
        if temp_out and temp_out.exists():
            try:
                temp_out.unlink()
            except OSError:
                pass


def cmd_send(args: argparse.Namespace) -> int:
    root = codex_home()
    codex_bin = ensure_codex_binary()

    target = args.target
    prompt_arg = args.prompt_opt or args.prompt
    if args.last and prompt_arg is None and target is not None:
        prompt_arg = target
        target = None

    prompt = read_prompt(prompt_arg, args.prompt_file)

    session = resolve_session(root, target, use_last=args.last, cwd=args.cwd)
    sid = str(session.get("id") or "")
    if not sid:
        raise SystemExit("Resolved session has no valid ID.")

    rollout_str = session.get("rollout_path")
    rollout_path = Path(str(rollout_str)).expanduser() if rollout_str else None
    locked = is_writer_locked(root, sid)
    running = is_turn_running(rollout_path) if locked else False

    if not args.force and running:
        raise SystemExit(
            f"Refusing to send: session {sid} has an active turn running in another Codex process. "
            "Wait until it completes or pass --force."
        )
    if not args.force and locked:
        raise SystemExit(
            f"Refusing to send: session {sid} currently holds an active writer lock (likely open in Codex App/TUI), "
            "so `codex exec resume` will fail with `already has an active writer`. "
            "Close/unload the thread in Codex App first or pass --force."
        )

    model = args.model or resolve_default_model(root)
    reasoning_effort = args.reasoning_effort

    cmd = [codex_bin, "exec", "resume", "--json"]
    if args.all:
        cmd.append("--all")
    if args.skip_git_repo_check:
        cmd.append("--skip-git-repo-check")
    if model:
        cmd.extend(["-m", model])
    if reasoning_effort:
        cmd.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])
    if args.sandbox:
        cmd.extend(["-c", f'sandbox_mode="{args.sandbox}"'])
    for img in args.image or []:
        cmd.extend(["-i", img])
    cmd.append(sid)

    exec_cwd = None
    session_cwd = str(session.get("cwd") or "").strip()
    if args.exec_cwd:
        exec_cwd = str(Path(args.exec_cwd).expanduser())
    elif session_cwd and Path(session_cwd).is_dir():
        exec_cwd = session_cwd

    return run_codex_exec(
        cmd,
        prompt,
        dry_run=args.dry_run,
        want_json=args.json,
        output_file=args.output_file,
        exec_cwd=exec_cwd,
        model=model,
        reasoning_effort=reasoning_effort,
    )


def cmd_start(args: argparse.Namespace) -> int:
    root = codex_home()
    codex_bin = ensure_codex_binary()
    prompt = read_prompt(args.prompt, args.prompt_file)

    model = args.model or resolve_default_model(root)
    reasoning_effort = args.reasoning_effort

    cmd = [codex_bin, "exec", "--json"]
    if args.cwd:
        cmd.extend(["-C", str(Path(args.cwd).expanduser())])
    if args.sandbox:
        cmd.extend(["-s", args.sandbox])
    if model:
        cmd.extend(["-m", model])
    if reasoning_effort:
        cmd.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])
    if args.skip_git_repo_check:
        cmd.append("--skip-git-repo-check")
    if args.ephemeral:
        cmd.append("--ephemeral")
    for img in args.image or []:
        cmd.extend(["-i", img])

    return run_codex_exec(
        cmd,
        prompt,
        dry_run=args.dry_run,
        want_json=args.json,
        output_file=args.output_file,
        model=model,
        reasoning_effort=reasoning_effort,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bridge to read and drive local Codex CLI/App sessions.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List recent Codex sessions.")
    p_list.add_argument("--cwd", help="Filter by working directory substring.")
    p_list.add_argument("--query", "-q", help="Filter by title/name/preview/branch substring.")
    p_list.add_argument("--limit", "-n", type=int, default=20, help="Max rows to show (default: 20, 0=all).")
    p_list.add_argument("--include-archived", action="store_true", help="Include archived sessions.")
    p_list.add_argument("--include-subagents", action="store_true", help="Include spawned subagent sessions.")
    p_list.add_argument("--json", action="store_true", help="Output JSON.")
    p_list.set_defaults(func=cmd_list)

    p_read = sub.add_parser("read", help="Read cleaned messages from a Codex session.")
    p_read.add_argument("target", nargs="?", help="Session UUID, UUID prefix, thread name, or title query.")
    p_read.add_argument("--last", action="store_true", help="Read the most recent active session.")
    p_read.add_argument("--cwd", help="Disambiguate --last or query by cwd substring.")
    p_read.add_argument("--last-turns", type=int, default=20, help="Show last N items (default: 20, 0=all).")
    p_read.add_argument("--offset", type=int, default=0, help="0-based item offset for pagination.")
    p_read.add_argument("--limit", type=int, default=0, help="Number of items to show with --offset.")
    p_read.add_argument("--max-chars", type=int, default=4000, help="Truncate individual items to N chars (0=no limit).")
    p_read.add_argument("--include-tools", action="store_true", help="Include tool calls and outputs.")
    p_read.add_argument("--final-only", action="store_true", help="Only show assistant final_answer messages.")
    p_read.add_argument("--include-boilerplate", action="store_true", help="Keep injected environment/AGENTS blocks.")
    p_read.add_argument("--json", action="store_true", help="Output JSON.")
    p_read.set_defaults(func=cmd_read)

    p_search = sub.add_parser("search", help="Search message text across recent Codex sessions.")
    p_search.add_argument("keyword", help="Case-insensitive substring to search.")
    p_search.add_argument("--cwd", help="Filter by working directory substring.")
    p_search.add_argument("--days", type=int, default=30, help="Only scan sessions updated within N days (default: 30, 0=all).")
    p_search.add_argument("--scan-limit", type=int, default=80, help="Max sessions to scan (default: 80).")
    p_search.add_argument("--limit", "-n", type=int, default=10, help="Max matched sessions to return (default: 10).")
    p_search.add_argument("--include-archived", action="store_true", help="Include archived sessions.")
    p_search.add_argument("--include-subagents", action="store_true", help="Include subagent sessions.")
    p_search.add_argument("--json", action="store_true", help="Output JSON.")
    p_search.set_defaults(func=cmd_search)

    p_send = sub.add_parser("send", help="Resume and send a prompt to an existing Codex session via `codex exec resume`.")
    p_send.add_argument("target", nargs="?", help="Session UUID, UUID prefix, or thread name.")
    p_send.add_argument("prompt", nargs="?", help="Prompt text (or '-' to read from stdin).")
    p_send.add_argument("-p", "--prompt", dest="prompt_opt", help="Explicit prompt text (handy with --last).")
    p_send.add_argument("--last", action="store_true", help="Target the most recent active session.")
    p_send.add_argument("--cwd", help="Disambiguate --last or target by cwd substring.")
    p_send.add_argument("--exec-cwd", help="Override subprocess working directory (defaults to the session's recorded cwd if it exists).")
    p_send.add_argument("--prompt-file", help="Read prompt from a file instead of CLI argument.")
    p_send.add_argument(
        "--sandbox",
        choices=["read-only", "workspace-write", "danger-full-access"],
        default="read-only",
        help="Codex sandbox mode override (default: read-only).",
    )
    p_send.add_argument("-m", "--model", help="Override model (defaults to top visible model in models_cache.json).")
    p_send.add_argument(
        "-r",
        "--reasoning-effort",
        default="high",
        help="Reasoning effort override passed via model_reasoning_effort (default: high).",
    )
    p_send.add_argument("-i", "--image", action="append", help="Attach image file(s).")
    p_send.add_argument("--all", action="store_true", default=True, help="Pass --all to codex exec resume (default: true).")
    p_send.add_argument("--skip-git-repo-check", action="store_true", help="Pass --skip-git-repo-check.")
    p_send.add_argument("--force", action="store_true", help="Send even if writer lock appears busy.")
    p_send.add_argument("-o", "--output-file", help="Save Codex final message to file.")
    p_send.add_argument("--dry-run", action="store_true", help="Print command without invoking Codex.")
    p_send.add_argument("--json", action="store_true", help="Output JSON.")
    p_send.set_defaults(func=cmd_send)

    p_start = sub.add_parser("start", help="Start a new non-interactive Codex session via `codex exec`.")
    p_start.add_argument("prompt", nargs="?", help="Prompt text (or '-' to read from stdin).")
    p_start.add_argument("--prompt-file", help="Read prompt from a file.")
    p_start.add_argument("-C", "--cwd", help="Working directory for the new Codex session.")
    p_start.add_argument(
        "--sandbox",
        choices=["read-only", "workspace-write", "danger-full-access"],
        default="read-only",
        help="Codex sandbox mode (default: read-only).",
    )
    p_start.add_argument("-m", "--model", help="Override model (defaults to top visible model in models_cache.json).")
    p_start.add_argument(
        "-r",
        "--reasoning-effort",
        default="high",
        help="Reasoning effort override passed via model_reasoning_effort (default: high).",
    )
    p_start.add_argument("-i", "--image", action="append", help="Attach image file(s).")
    p_start.add_argument("--skip-git-repo-check", action="store_true", help="Allow running outside a Git repo.")
    p_start.add_argument("--ephemeral", action="store_true", help="Do not persist session files to disk.")
    p_start.add_argument("-o", "--output-file", help="Save Codex final message to file.")
    p_start.add_argument("--dry-run", action="store_true", help="Print command without invoking Codex.")
    p_start.add_argument("--json", action="store_true", help="Output JSON.")
    p_start.set_defaults(func=cmd_start)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
