#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="${SRC_DIR:-$REPO_ROOT/skills}"
DEST_DIR="${DEST_DIR:-${HOME}/.codex/skills}"
CUSTOM_CATALOG_PATH="${CUSTOM_CATALOG_PATH:-$REPO_ROOT/catalog/custom.yaml}"
BUILTIN_CATALOG_PATH="${BUILTIN_CATALOG_PATH:-$REPO_ROOT/catalog/builtins.yaml}"
THIRD_PARTY_CATALOG_PATH="${THIRD_PARTY_CATALOG_PATH:-$REPO_ROOT/catalog/third-party.yaml}"
VENDOR_DIR="${VENDOR_DIR:-$REPO_ROOT/vendor}"
STRICT_BUILTINS="${STRICT_BUILTINS:-0}"

parse_catalog() {
  python3 - "$1" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)

items = []
current = None

def convert(value: str):
    value = value.strip()
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        value = value[1:-1]
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
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

for item in items:
    print(json.dumps(item, ensure_ascii=True))
PY
}

link_skill() {
  local source_dir="$1"
  local target="$2"
  local name
  name="$(basename "$target")"

  if [ -L "$target" ]; then
    local current
    current="$(readlink "$target" || true)"
    if [ "$current" = "$source_dir" ]; then
      echo "ok: $name already linked"
      return 0
    fi
    echo "skip: $name already exists locally"
    return 0
  elif [ -e "$target" ]; then
    echo "skip: $name already exists locally"
    return 0
  fi

  mkdir -p "$(dirname "$target")"
  ln -s "$source_dir" "$target"
  echo "linked: $name"
}

install_custom_skills() {
  if [ -f "$CUSTOM_CATALOG_PATH" ]; then
    while IFS= read -r item; do
      [ -n "$item" ] || continue

      local enabled name skill_dir target
      enabled="$(python3 -c 'import json,sys; print("true" if json.loads(sys.argv[1]).get("enabled", False) else "false")' "$item")"
      [ "$enabled" = "true" ] || continue

      name="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("name", ""))' "$item")"
      skill_dir="$SRC_DIR/$name"
      target="$DEST_DIR/$name"

      if [ ! -f "$skill_dir/SKILL.md" ]; then
        echo "warning: custom skill $name is enabled but missing from $skill_dir" >&2
        continue
      fi

      link_skill "$skill_dir" "$target"
    done < <(parse_catalog "$CUSTOM_CATALOG_PATH")
    return 0
  fi

  for skill_dir in "$SRC_DIR"/*; do
    [ -d "$skill_dir" ] || continue
    local name target
    name="$(basename "$skill_dir")"
    target="$DEST_DIR/$name"
    link_skill "$skill_dir" "$target"
  done
}

check_builtin_skills() {
  local missing_required=0

  [ -f "$BUILTIN_CATALOG_PATH" ] || return 0

  while IFS= read -r item; do
    [ -n "$item" ] || continue

    local rel_path required target
    rel_path="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("path") or json.loads(sys.argv[1]).get("name") or "")' "$item")"
    required="$(python3 -c 'import json,sys; print("true" if json.loads(sys.argv[1]).get("required", False) else "false")' "$item")"
    target="$DEST_DIR/$rel_path"

    if [ -f "$target/SKILL.md" ]; then
      echo "builtin: found $rel_path"
      continue
    fi

    if [ "$required" = "true" ]; then
      echo "warning: missing required builtin skill $rel_path" >&2
      missing_required=1
    else
      echo "warning: missing optional builtin skill $rel_path" >&2
    fi
  done < <(parse_catalog "$BUILTIN_CATALOG_PATH")

  if [ "$missing_required" -eq 1 ] && [ "$STRICT_BUILTINS" = "1" ]; then
    echo "error: missing required builtin skill(s) while STRICT_BUILTINS=1" >&2
    return 1
  fi
}

sync_third_party_skills() {
  [ -f "$THIRD_PARTY_CATALOG_PATH" ] || return 0

  mkdir -p "$VENDOR_DIR"

  while IFS= read -r item; do
    [ -n "$item" ] || continue

    local enabled source_type name repo branch skill_path checkout_name checkout_dir source_dir target
    enabled="$(python3 -c 'import json,sys; print("true" if json.loads(sys.argv[1]).get("enabled", False) else "false")' "$item")"
    [ "$enabled" = "true" ] || continue

    source_type="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("source", ""))' "$item")"
    name="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("name", ""))' "$item")"

    if [ "$source_type" != "git" ]; then
      echo "warning: unsupported third-party source '$source_type' for $name" >&2
      continue
    fi

    target="$DEST_DIR/$name"
    if [ -e "$target" ] || [ -L "$target" ]; then
      echo "skip: $name already exists locally"
      continue
    fi

    repo="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("repo", ""))' "$item")"
    branch="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("branch", "main"))' "$item")"
    skill_path="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("skill_path", "."))' "$item")"
    checkout_name="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("checkout", json.loads(sys.argv[1]).get("name", "")))' "$item")"
    checkout_dir="$VENDOR_DIR/$checkout_name"

    if [ -d "$checkout_dir/.git" ]; then
      git -C "$checkout_dir" fetch --all --prune
      git -C "$checkout_dir" checkout "$branch"
      git -C "$checkout_dir" pull --ff-only origin "$branch"
    else
      git clone --branch "$branch" "$repo" "$checkout_dir"
    fi

    source_dir="$checkout_dir/$skill_path"

    if [ ! -f "$source_dir/SKILL.md" ]; then
      echo "warning: third-party skill $name missing SKILL.md at $skill_path" >&2
      continue
    fi

    link_skill "$source_dir" "$target"
  done < <(parse_catalog "$THIRD_PARTY_CATALOG_PATH")
}

echo "Installing skills from: $SRC_DIR"
echo "Into: $DEST_DIR"
echo "Custom catalog: $CUSTOM_CATALOG_PATH"
echo "Builtin catalog: $BUILTIN_CATALOG_PATH"
echo "Third-party catalog: $THIRD_PARTY_CATALOG_PATH"

mkdir -p "$DEST_DIR"

install_custom_skills
check_builtin_skills
sync_third_party_skills

echo "Done."
