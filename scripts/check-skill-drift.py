#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def parse_simple_yaml_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def convert(value: str) -> Any:
        value = value.strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        return value

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("- "):
            if current is not None:
                items.append(current)
            current = {}
            remainder = line[2:].strip()
            if remainder and ":" in remainder:
                key, value = remainder.split(":", 1)
                current[key.strip()] = convert(value)
            continue
        if line.startswith("  ") and ":" in stripped and current is not None:
            key, value = stripped.split(":", 1)
            current[key.strip()] = convert(value)

    if current is not None:
        items.append(current)
    return items


def find_local_skills(skills_root: Path) -> list[str]:
    skills: list[str] = []
    for skill_file in sorted(skills_root.rglob("SKILL.md")):
        rel = skill_file.parent.relative_to(skills_root).as_posix()
        skills.append(rel)
    return skills


def classify_skill(
    rel_path: str,
    builtin_paths: set[str],
    custom_names: set[str],
    third_party_names: set[str],
) -> str:
    name = Path(rel_path).name
    if rel_path in builtin_paths:
        return "builtin"
    if name in custom_names:
        return "custom"
    if name in third_party_names:
        return "third_party"
    return "unknown"


def build_snapshot(
    skills_root: Path,
    builtins_path: Path,
    custom_path: Path,
    third_party_path: Path,
) -> dict[str, Any]:
    builtins = parse_simple_yaml_list(builtins_path)
    custom = parse_simple_yaml_list(custom_path)
    third_party = parse_simple_yaml_list(third_party_path)

    builtin_paths = {
        str(item.get("path") or item.get("name") or "").strip()
        for item in builtins
        if (item.get("path") or item.get("name"))
    }
    custom_names = {
        str(item.get("name") or "").strip()
        for item in custom
        if item.get("name") and item.get("enabled", False)
    }
    third_party_names = {
        str(item.get("name") or "").strip()
        for item in third_party
        if item.get("name") and item.get("enabled", False)
    }

    rows = []
    for rel_path in find_local_skills(skills_root):
        source = classify_skill(rel_path, builtin_paths, custom_names, third_party_names)
        rows.append({"path": rel_path, "source": source})

    rows.sort(key=lambda row: row["path"])

    payload = {
        "skills_root": str(skills_root),
        "rows": rows,
        "summary": {
            "total": len(rows),
            "builtin": sum(1 for row in rows if row["source"] == "builtin"),
            "custom": sum(1 for row in rows if row["source"] == "custom"),
            "third_party": sum(1 for row in rows if row["source"] == "third_party"),
            "unknown": sum(1 for row in rows if row["source"] == "unknown"),
        },
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(payload["rows"], ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return payload


def load_previous_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def diff_rows(old_rows: list[dict[str, Any]], new_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    old_map = {row["path"]: row["source"] for row in old_rows}
    new_map = {row["path"]: row["source"] for row in new_rows}

    added = sorted(path for path in new_map.keys() - old_map.keys())
    removed = sorted(path for path in old_map.keys() - new_map.keys())
    changed = sorted(
        path for path in new_map.keys() & old_map.keys() if new_map[path] != old_map[path]
    )
    unknown = sorted(path for path, source in new_map.items() if source == "unknown")

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "unknown": unknown,
    }


def print_report(snapshot: dict[str, Any], diff: dict[str, list[str]] | None, changed: bool) -> None:
    summary = snapshot["summary"]
    print(f"changed={'yes' if changed else 'no'}")
    print(
        "summary="
        f"total:{summary['total']}, builtin:{summary['builtin']}, custom:{summary['custom']}, "
        f"third_party:{summary['third_party']}, unknown:{summary['unknown']}"
    )
    if not diff:
        return
    for key in ["added", "removed", "changed", "unknown"]:
        values = diff[key]
        if values:
            print(f"{key}=" + ", ".join(values))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-root", required=True)
    parser.add_argument("--builtins", required=True)
    parser.add_argument("--custom", required=True)
    parser.add_argument("--third-party", required=True)
    parser.add_argument("--state-file", required=True)
    parser.add_argument("--write-state", action="store_true")
    args = parser.parse_args()

    snapshot = build_snapshot(
        Path(args.skills_root).expanduser(),
        Path(args.builtins).expanduser(),
        Path(args.custom).expanduser(),
        Path(args.third_party).expanduser(),
    )

    state_file = Path(args.state_file).expanduser()
    previous = load_previous_state(state_file)
    changed = previous is None or previous.get("fingerprint") != snapshot["fingerprint"]
    diff = None
    if previous is not None:
        diff = diff_rows(previous.get("rows", []), snapshot["rows"])

    print_report(snapshot, diff, changed)

    if args.write_state:
        save_state(state_file, snapshot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
