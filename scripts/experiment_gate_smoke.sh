#!/usr/bin/env bash
#
# Smoke test for experiment-gate.yaml.
#
# Verifies the experiment-worker phase gate:
#   1. `git push`   under phase experiment-worker  -> DENY
#   2. `git commit` under phase experiment-worker  -> allow
#   3. `git push`   under phase planning           -> allow (rule scoped to phase)
#
# Uses throwaway session ids and deletes their state files afterward.
# No live session state is touched.

set -u

WARD_BIN="${WARD_BIN:-C:/Users/Q/go/bin/ward.exe}"
RULES_DIR="C:/Users/Q/code/protocols-plugin/plugins/protocols/ward-profile/rules"
export WARD_RULES_PATH="$RULES_DIR"

STATE_DIR="$TEMP/ward"
SID_WORKER="expgate-smoke-worker-$$"
SID_PLANNING="expgate-smoke-planning-$$"

fail=0

cleanup() {
  rm -f "$STATE_DIR/$SID_WORKER.json" "$STATE_DIR/$SID_PLANNING.json"
}
trap cleanup EXIT

# Emit a PreToolUse Bash event JSON for the given command + session id.
event() {
  local cmd="$1" sid="$2"
  printf '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"%s"},"session_id":"%s","cwd":"C:/Users/Q/code/protocols-plugin"}' "$cmd" "$sid"
}

# Run one case. Args: description, command, session, expected (DENY|ALLOW)
run_case() {
  local desc="$1" cmd="$2" sid="$3" expect="$4"
  local out
  out="$(event "$cmd" "$sid" | "$WARD_BIN" eval -v 2>/dev/null)"
  local got="ALLOW"
  if printf '%s' "$out" | grep -q "Experiment protocol active"; then
    got="DENY"
  fi
  echo "=== $desc"
  echo "    command : $cmd"
  echo "    phase   : $(basename "$sid")"
  echo "    expected: $expect   got: $got"
  echo "    stdout  : $out"
  if [ "$got" != "$expect" ]; then
    echo "    RESULT  : MISMATCH"
    fail=1
  else
    echo "    RESULT  : OK"
  fi
  echo
}

echo "### ward validate (compile check of effective ruleset incl. experiment-gate.yaml)"
"$WARD_BIN" validate
echo

echo "### Setting up throwaway sessions"
"$WARD_BIN" set experiment-worker --session "$SID_WORKER" >/dev/null
"$WARD_BIN" set planning --session "$SID_PLANNING" >/dev/null
echo

run_case "git push under experiment-worker"   "git push"        "$SID_WORKER"   "DENY"
run_case "git commit under experiment-worker" "git commit -m x" "$SID_WORKER"   "ALLOW"
run_case "git push under planning"            "git push"        "$SID_PLANNING" "ALLOW"

if [ "$fail" -eq 0 ]; then
  echo "ALL SMOKE CASES PASSED"
else
  echo "SMOKE FAILURE"
fi
exit "$fail"
