#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

SKILLS_ROOT="$TMP_DIR/skills"
mkdir -p "$SKILLS_ROOT/.system/imagegen" "$SKILLS_ROOT/foo-custom" "$SKILLS_ROOT/bar-third" "$SKILLS_ROOT/unknown-skill"

for dir in "$SKILLS_ROOT/.system/imagegen" "$SKILLS_ROOT/foo-custom" "$SKILLS_ROOT/bar-third" "$SKILLS_ROOT/unknown-skill"; do
  cat > "$dir/SKILL.md" <<'EOF'
---
name: sample
description: sample
---
EOF
done

BUILTINS="$TMP_DIR/builtins.yaml"
cat > "$BUILTINS" <<'EOF'
- name: imagegen
  path: .system/imagegen
  required: true
EOF

CUSTOM="$TMP_DIR/custom.yaml"
cat > "$CUSTOM" <<'EOF'
- name: foo-custom
  enabled: true
EOF

THIRD="$TMP_DIR/third-party.yaml"
cat > "$THIRD" <<'EOF'
- name: bar-third
  source: git
  repo: https://example.com/repo.git
  branch: main
  checkout: repo
  skill_path: skills/bar-third
  enabled: true
EOF

OUTPUT="$TMP_DIR/report.md"
python3 "$REPO_ROOT/scripts/audit-local-skills.py" \
  --skills-root "$SKILLS_ROOT" \
  --builtins "$BUILTINS" \
  --custom "$CUSTOM" \
  --third-party "$THIRD" \
  --output "$OUTPUT"

grep -q '| `.system/imagegen` | `builtin` |' "$OUTPUT"
grep -q '| `foo-custom` | `custom` |' "$OUTPUT"
grep -q '| `bar-third` | `third_party` |' "$OUTPUT"
grep -q '| `unknown-skill` | `unknown` |' "$OUTPUT"

echo "PASS: audit-local-skills classifies builtin, custom, third-party, and unknown skills"
