#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def parse_simple_yaml_list(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []

    items: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    def convert(value: str) -> object:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skills-root", required=True)
    parser.add_argument("--builtins", required=True)
    parser.add_argument("--custom", required=True)
    parser.add_argument("--third-party", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    skills_root = Path(args.skills_root).expanduser()
    builtins = parse_simple_yaml_list(Path(args.builtins).expanduser())
    custom = parse_simple_yaml_list(Path(args.custom).expanduser())
    third_party = parse_simple_yaml_list(Path(args.third_party).expanduser())

    builtin_paths = {
        str(item.get("path") or item.get("name") or "").strip()
        for item in builtins
        if (item.get("path") or item.get("name"))
    }
    custom_names = {
        str(item.get("name") or "").strip()
        for item in custom
        if item.get("name")
    }
    third_party_names = {
        str(item.get("name") or "").strip()
        for item in third_party
        if item.get("name")
    }

    rows = []
    for rel_path in find_local_skills(skills_root):
        source = classify_skill(rel_path, builtin_paths, custom_names, third_party_names)
        rows.append((rel_path, source))

    unknown_count = sum(1 for _, source in rows if source == "unknown")
    lines = [
        "# Local Skills Source Audit",
        "",
        f"- Skills root: `{skills_root}`",
        f"- Total skills found: `{len(rows)}`",
        f"- Unknown skills: `{unknown_count}`",
        "",
        "| Local Path | Source |",
        "| --- | --- |",
    ]
    for rel_path, source in rows:
        lines.append(f"| `{rel_path}` | `{source}` |")

    Path(args.output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
