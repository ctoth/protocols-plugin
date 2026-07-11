#!/usr/bin/env bash
# Focused actor-key smoke test for experiment-worker restrictions.

set -u

if [ -z "${WARD_BIN:-}" ] && [ -x /mnt/c/Users/Q/go/bin/ward.exe ]; then
  WARD_BIN=/mnt/c/Users/Q/go/bin/ward.exe
else
  WARD_BIN="${WARD_BIN:-C:/Users/Q/go/bin/ward.exe}"
fi
ROOT="${ROOT:-$PWD}"
RULES_DIR="${RULES_DIR:-$ROOT/plugins/protocols/ward-profile/rules}"
if command -v cygpath >/dev/null 2>&1; then
  RULES_DIR="$(cygpath -m "$RULES_DIR")"
elif command -v wslpath >/dev/null 2>&1; then
  RULES_DIR="$(wslpath -w "$RULES_DIR")"
fi
export WARD_RULES_PATH="$RULES_DIR"
SID="expgate-actor-family-$$"
WORKER_ID="experiment-worker-$$"
fail=0

cleanup() {
  jq -cn --arg sid "$SID" '{hook_event_name:"SessionEnd",session_id:$sid}' | "$WARD_BIN" end-session >/dev/null 2>&1 || true
}
trap cleanup EXIT

event() { # command, optional agent id/type
  jq -cn --arg command "$1" --arg sid "$SID" --arg agent "$2" --arg type "$3" \
    '{hook_event_name:"PreToolUse",tool_name:"Bash",tool_input:{command:$command},
      session_id:$sid,cwd:"C:/Users/Q/code/protocols-plugin"}
      + (if $agent == "" then {} else {agent_id:$agent,agent_type:$type} end)'
}

run_case() { # description, command, agent id, expected
  local out got
  out="$(event "$2" "$3" "experiment-worker" | "$WARD_BIN" eval -v 2>&1)"
  got="ALLOW"
  if printf '%s' "$out" | grep -q 'permissionDecision.*deny'; then got="DENY"; fi
  printf '=== %s\n    expected: %s   got: %s\n' "$1" "$4" "$got"
  if [ "$got" != "$4" ]; then
    printf '    stdout: %s\n' "$out"
    fail=1
  fi
}

"$WARD_BIN" validate
"$WARD_BIN" set planning --session "$SID" >/dev/null
"$WARD_BIN" set experiment-worker --session "$SID" --agent "$WORKER_ID" >/dev/null

run_case "worker git push denied" "git push" "$WORKER_ID" DENY
run_case "worker git commit allowed" "git commit -m x" "$WORKER_ID" ALLOW
run_case "main git push allowed" "git push" "" ALLOW
run_case "worker remains restricted after main action" "git push" "$WORKER_ID" DENY

if [ "$fail" -eq 0 ]; then
  echo "ALL ACTOR-SCOPED EXPERIMENT CASES PASSED"
else
  echo "ACTOR-SCOPED EXPERIMENT FAILURE"
fi
exit "$fail"
