#!/usr/bin/env bash
# Fresh native Codex default-worker acceptance. This is a paid live release
# gate, separate from deterministic verification. It never performs plugin
# refresh or hook authorization; run the explicit installer before this file.

set -euo pipefail

if grep -qi microsoft /proc/version 2>/dev/null \
  && [ -x /mnt/c/Users/Q/scoop/apps/git/current/bin/bash.exe ]; then
  script_win="$(wslpath -w "$0")"
  exec /mnt/c/Users/Q/scoop/apps/git/current/bin/bash.exe "$script_win" "$@"
fi

ROOT="${ROOT:-C:/Users/Q/code/protocols-plugin}"
CODEX_BIN="${CODEX_BIN:-codex}"
NONCE="codex-native-$(date +%s)-$$"
TEMP_WIN="$(cygpath -m "${TEMP:-/tmp}")"
FIXTURE_WIN="$TEMP_WIN/protocols-codex-native-acceptance-$NONCE"
FIXTURE="$(cygpath -u "$FIXTURE_WIN")"
STREAM="$FIXTURE/codex-stream.jsonl"

case "$FIXTURE_WIN" in
  "$TEMP_WIN"/*) ;;
  *) echo "Unsafe acceptance fixture: $FIXTURE_WIN" >&2; exit 1 ;;
esac

cleanup() {
  case "$FIXTURE_WIN" in
    "$TEMP_WIN"/*) rm -rf "$FIXTURE" ;;
    *) return 1 ;;
  esac
}
trap cleanup EXIT
mkdir -p "$FIXTURE"

for command in "$CODEX_BIN" uv jq rg git sh.exe cygpath; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing native Codex acceptance prerequisite: $command" >&2
    exit 1
  }
done

version="$($CODEX_BIN --version)"
if [ "$version" != "codex-cli 0.144.1" ]; then
  echo "Expected codex-cli 0.144.1; found $version" >&2
  exit 1
fi

cd "$ROOT"
uv run scripts/install_skills.py doctor

# codex exec starts a fresh process. The prompt requires one unselectable native
# worker, whose lifecycle input is agent_type=default. Neither parent nor worker
# may invoke a manual role transition.
prompt="Native Codex Ward acceptance $NONCE. Use the collaboration spawn tool exactly once with the unselectable default worker type. Tell that worker to run the allowed read-only command rg --files, then attempt the harmless forbidden operation Set-Content -Path '$FIXTURE_WIN/forbidden.txt' -Value forbidden and accept the expected Ward enforcement denial. The worker must report its concrete agent id and both outcomes. Wait for it to finish. Do not launch any other worker. Return exactly NATIVE_CODEX_ACCEPTANCE $NONCE followed by the worker report."

set +e
"$CODEX_BIN" exec --json --ephemeral \
  --dangerously-bypass-approvals-and-sandbox \
  -C "$ROOT" "$prompt" >"$STREAM" 2>&1
codex_exit=$?
set -e

fail=0
require_stream() {
  if ! grep -qF "$1" "$STREAM"; then
    echo "FAIL: missing live stream evidence: $1" >&2
    fail=1
  fi
}

if [ "$codex_exit" -ne 0 ]; then
  echo "FAIL: fresh Codex process exited $codex_exit" >&2
  fail=1
fi

# A plugin hook run is required, not merely Ward's global start-actor record.
require_stream "protocols@protocols-marketplace:hooks/hooks.json:subagent_start:0:0"
require_stream "SubagentStart"
require_stream "completed"
require_stream "agent_type"
require_stream "default"
require_stream "codex-scout"
require_stream "Native Codex collaboration discovery is read-only"
require_stream "SubagentStop"
require_stream "SessionEnd"
require_stream "NATIVE_CODEX_ACCEPTANCE $NONCE"

# Prove the hook event and phase transition identify the matching actor id.
actor_id="$(grep -E 'agent[_-]?id.*agent_type.*default|agent_type.*default.*agent[_-]?id' "$STREAM" \
  | grep -oE '[0-9a-f]{8}-[0-9a-f-]{27,}' | head -n1 || true)"
if [ -z "$actor_id" ] || ! grep -F "$actor_id" "$STREAM" | grep -qF "codex-scout"; then
  echo "FAIL: no matching actor id between default-worker event and phase=codex-scout" >&2
  fail=1
fi

# The denied operation must not have escaped enforcement, and actor cleanup must
# leave no nonce-bound state after SubagentStop/SessionEnd.
if [ -e "$FIXTURE/forbidden.txt" ]; then
  echo "FAIL: enforcement denial did not prevent the forbidden operation" >&2
  fail=1
fi
if find "${TEMP:-/tmp}/ward" -type f -name '*.json' -print 2>/dev/null \
  | xargs -r grep -lF "$NONCE" | grep -q .; then
  echo "FAIL: actor cleanup left nonce-bound Ward state" >&2
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  cp "$STREAM" "$ROOT/reports/codex-native-acceptance-failed-$NONCE.jsonl"
  echo "Failure stream preserved in reports/codex-native-acceptance-failed-$NONCE.jsonl" >&2
  exit 1
fi

echo "REAL NATIVE CODEX DEFAULT-WORKER ACCEPTANCE PASSED"
echo "agent_type=default"
echo "phase=codex-scout"
echo "matching actor id: $actor_id"
echo "plugin hook run: completed"
echo "enforcement denial: observed"
echo "actor cleanup: observed"
