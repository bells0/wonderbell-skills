#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

DEST_DIR="$TMP_DIR/dest-skills"
mkdir -p "$DEST_DIR"

BUILTIN_CATALOG_PATH="$TMP_DIR/builtins.yaml"
cat > "$BUILTIN_CATALOG_PATH" <<'EOF'
- name: missing-builtin
  type: builtin
  required: true
EOF

OUTPUT="$TMP_DIR/output.txt"

set +e
DEST_DIR="$DEST_DIR" \
BUILTIN_CATALOG_PATH="$BUILTIN_CATALOG_PATH" \
STRICT_BUILTINS=1 \
bash "$REPO_ROOT/scripts/install.sh" >"$OUTPUT" 2>&1
STATUS=$?
set -e

if [ "$STATUS" -eq 0 ]; then
  echo "expected installer to fail when a required builtin skill is missing"
  cat "$OUTPUT"
  exit 1
fi

if ! grep -q "missing required builtin skill" "$OUTPUT"; then
  echo "expected missing builtin error message"
  cat "$OUTPUT"
  exit 1
fi

echo "PASS: installer fails in strict mode when required builtin skill is missing"
