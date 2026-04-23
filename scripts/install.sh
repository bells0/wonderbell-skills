#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$REPO_ROOT/skills"
DEST_DIR="${HOME}/.codex/skills"

mkdir -p "$DEST_DIR"

echo "Installing skills from: $SRC_DIR"
echo "Into: $DEST_DIR"

for skill_dir in "$SRC_DIR"/*; do
  [ -d "$skill_dir" ] || continue
  name="$(basename "$skill_dir")"
  target="$DEST_DIR/$name"

  if [ -L "$target" ]; then
    current="$(readlink "$target" || true)"
    if [ "$current" = "$skill_dir" ]; then
      echo "ok: $name already linked"
      continue
    fi
    rm "$target"
  elif [ -e "$target" ]; then
    echo "error: $target exists and is not a symlink; refusing to overwrite" >&2
    exit 1
  fi

  ln -s "$skill_dir" "$target"
  echo "linked: $name"
done

echo "Done."
