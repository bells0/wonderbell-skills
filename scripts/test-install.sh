#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

run_missing_builtin_test() {
  local dest_dir="$TMP_DIR/dest-builtins"
  mkdir -p "$dest_dir"

  local builtin_catalog_path="$TMP_DIR/builtins.yaml"
  cat > "$builtin_catalog_path" <<'EOF'
- name: missing-builtin
  type: builtin
  required: true
EOF

  local output="$TMP_DIR/output-builtins.txt"

  set +e
  DEST_DIR="$dest_dir" \
  BUILTIN_CATALOG_PATH="$builtin_catalog_path" \
  STRICT_BUILTINS=1 \
  bash "$REPO_ROOT/scripts/install.sh" >"$output" 2>&1
  local status=$?
  set -e

  if [ "$status" -eq 0 ]; then
    echo "expected installer to fail when a required builtin skill is missing"
    cat "$output"
    exit 1
  fi

  if ! grep -q "missing required builtin skill" "$output"; then
    echo "expected missing builtin error message"
    cat "$output"
    exit 1
  fi
}

run_custom_install_test() {
  local src_dir="$TMP_DIR/custom-src"
  local dest_dir="$TMP_DIR/custom-dest"
  mkdir -p "$src_dir/alpha" "$src_dir/beta" "$dest_dir/alpha"

  cat > "$src_dir/alpha/SKILL.md" <<'EOF'
---
name: alpha
description: Use when testing installer behavior
---
EOF

  cat > "$src_dir/beta/SKILL.md" <<'EOF'
---
name: beta
description: Use when testing disabled custom skills
---
EOF

  cat > "$dest_dir/alpha/SKILL.md" <<'EOF'
preexisting
EOF

  local custom_catalog_path="$TMP_DIR/custom.yaml"
  cat > "$custom_catalog_path" <<'EOF'
- name: alpha
  enabled: true
- name: beta
  enabled: false
EOF

  local output="$TMP_DIR/output-custom.txt"
  DEST_DIR="$dest_dir" \
  SRC_DIR="$src_dir" \
  CUSTOM_CATALOG_PATH="$custom_catalog_path" \
  BUILTIN_CATALOG_PATH="$TMP_DIR/empty-builtins.yaml" \
  THIRD_PARTY_CATALOG_PATH="$TMP_DIR/empty-third-party.yaml" \
  bash "$REPO_ROOT/scripts/install.sh" >"$output" 2>&1

  if [ -L "$dest_dir/alpha" ]; then
    echo "expected existing local alpha skill to be left untouched"
    cat "$output"
    exit 1
  fi

  if [ -e "$dest_dir/beta" ]; then
    echo "expected disabled beta skill to remain uninstalled"
    cat "$output"
    exit 1
  fi

  if ! grep -q "skip: alpha already exists locally" "$output"; then
    echo "expected installer to report skipped local skill"
    cat "$output"
    exit 1
  fi
}

run_third_party_install_test() {
  local repo_dir="$TMP_DIR/third-party-repo"
  local worktree_dir="$TMP_DIR/third-party-worktree"
  local dest_dir="$TMP_DIR/third-party-dest"
  local vendor_dir="$TMP_DIR/vendor"

  mkdir -p "$repo_dir" "$dest_dir"
  git -C "$repo_dir" init --bare >/dev/null 2>&1

  git clone "$repo_dir" "$worktree_dir" >/dev/null 2>&1
  mkdir -p "$worktree_dir/skills/sample-third-party"
  cat > "$worktree_dir/skills/sample-third-party/SKILL.md" <<'EOF'
---
name: sample-third-party
description: Use when testing third-party installer behavior
---
EOF
  git -C "$worktree_dir" add skills/sample-third-party/SKILL.md
  git -C "$worktree_dir" -c user.name='Test User' -c user.email='test@example.com' commit -m 'Add sample skill' >/dev/null 2>&1
  git -C "$worktree_dir" push origin HEAD:main >/dev/null 2>&1

  local third_party_catalog_path="$TMP_DIR/third-party.yaml"
  cat > "$third_party_catalog_path" <<EOF
- name: sample-third-party
  source: git
  repo: $repo_dir
  branch: main
  skill_path: skills/sample-third-party
  enabled: true
EOF

  local output="$TMP_DIR/output-third-party.txt"
  DEST_DIR="$dest_dir" \
  SRC_DIR="$TMP_DIR/empty-custom-src" \
  CUSTOM_CATALOG_PATH="$TMP_DIR/empty-custom.yaml" \
  BUILTIN_CATALOG_PATH="$TMP_DIR/empty-builtins.yaml" \
  THIRD_PARTY_CATALOG_PATH="$third_party_catalog_path" \
  VENDOR_DIR="$vendor_dir" \
  bash "$REPO_ROOT/scripts/install.sh" >"$output" 2>&1

  if [ ! -L "$dest_dir/sample-third-party" ]; then
    echo "expected enabled third-party skill to be installed"
    cat "$output"
    exit 1
  fi
}

run_missing_builtin_test
run_custom_install_test
run_third_party_install_test

echo "PASS: install script handles strict builtin checks and custom on-demand installs"
