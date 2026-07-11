#!/usr/bin/env bash
# Full deterministic repository gate. The real Claude acceptance is a separate
# release gate because it launches paid external agents.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -z "${WARD_BIN:-}" ] && [ -x /mnt/c/Users/Q/go/bin/ward.exe ]; then
  WARD_BIN=/mnt/c/Users/Q/go/bin/ward.exe
elif [ -z "${WARD_BIN:-}" ] && command -v ward.exe >/dev/null 2>&1; then
  WARD_BIN=ward.exe
else
  WARD_BIN="${WARD_BIN:-ward}"
fi

uv run scripts/test_protocols_plugin.py
uv run scripts/lint_skill_frontmatter.py
if command -v wslpath >/dev/null 2>&1; then
  PROFILE_PATH="$(wslpath -w "$ROOT/plugins/protocols/ward-profile")"
else
  PROFILE_PATH="$ROOT/plugins/protocols/ward-profile"
fi
"$WARD_BIN" validate-profile "$PROFILE_PATH"
WARD_BIN="$WARD_BIN" bash ./scripts/ward_profile_verify.sh
WARD_BIN="$WARD_BIN" bash ./scripts/experiment_gate_smoke.sh
uv run scripts/install_skills.py doctor
git diff --check

echo "FULL REPOSITORY GATE PASSED"
