#!/usr/bin/env bash
# Fresh native Codex collaboration acceptance. This paid live release gate uses
# app-server typed notifications because codex exec JSON does not expose the
# child lifecycle and command evidence required by the contract.

set -euo pipefail

if grep -qi microsoft /proc/version 2>/dev/null \
  && [ -x /mnt/c/Users/Q/scoop/apps/git/current/bin/bash.exe ]; then
  script_win="$(wslpath -w "$0")"
  exec /mnt/c/Users/Q/scoop/apps/git/current/bin/bash.exe "$script_win" "$@"
fi

ROOT="${ROOT:-C:/Users/Q/code/protocols-plugin}"
cd "$ROOT"

command -v uv >/dev/null 2>&1 || {
  echo "Missing native Codex acceptance prerequisite: uv" >&2
  exit 1
}

uv run scripts/install_skills.py doctor
uv run scripts/codex_native_app_server_acceptance.py
