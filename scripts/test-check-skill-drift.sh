#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

SKILLS_ROOT="$TMP_DIR/skills"
mkdir -p "$SKILLS_ROOT/.system/imagegen" "$SKILLS_ROOT/my-custom"

for dir in "$SKILLS_ROOT/.system/imagegen" "$SKILLS_ROOT/my-custom"; do
  cat > "$dir/SKILL.md" <<'EOF'
---
name: sample
description: sample
---
EOF
done

cat > "$TMP_DIR/builtins.yaml" <<'EOF'
- name: imagegen
  path: .system/imagegen
  required: true
EOF

cat > "$TMP_DIR/custom.yaml" <<'EOF'
- name: my-custom
  enabled: true
EOF

cat > "$TMP_DIR/third-party.yaml" <<'EOF'
# empty
EOF

STATE_FILE="$TMP_DIR/state.json"
OUTPUT1="$TMP_DIR/output1.txt"
OUTPUT2="$TMP_DIR/output2.txt"
OUTPUT3="$TMP_DIR/output3.txt"

python3 "$REPO_ROOT/scripts/check-skill-drift.py" \
  --skills-root "$SKILLS_ROOT" \
  --builtins "$TMP_DIR/builtins.yaml" \
  --custom "$TMP_DIR/custom.yaml" \
  --third-party "$TMP_DIR/third-party.yaml" \
  --state-file "$STATE_FILE" \
  --write-state > "$OUTPUT1"

grep -q 'changed=yes' "$OUTPUT1"

python3 "$REPO_ROOT/scripts/check-skill-drift.py" \
  --skills-root "$SKILLS_ROOT" \
  --builtins "$TMP_DIR/builtins.yaml" \
  --custom "$TMP_DIR/custom.yaml" \
  --third-party "$TMP_DIR/third-party.yaml" \
  --state-file "$STATE_FILE" > "$OUTPUT2"

grep -q 'changed=no' "$OUTPUT2"

mkdir -p "$SKILLS_ROOT/unknown-skill"
cat > "$SKILLS_ROOT/unknown-skill/SKILL.md" <<'EOF'
---
name: unknown-skill
description: sample
---
EOF

python3 "$REPO_ROOT/scripts/check-skill-drift.py" \
  --skills-root "$SKILLS_ROOT" \
  --builtins "$TMP_DIR/builtins.yaml" \
  --custom "$TMP_DIR/custom.yaml" \
  --third-party "$TMP_DIR/third-party.yaml" \
  --state-file "$STATE_FILE" > "$OUTPUT3"

grep -q 'changed=yes' "$OUTPUT3"
grep -q 'added=unknown-skill' "$OUTPUT3"
grep -q 'unknown=unknown-skill' "$OUTPUT3"

echo "PASS: check-skill-drift reports changes only when local skill state changes"
