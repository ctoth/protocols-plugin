#!/usr/bin/env bash
#
# Verify the protocols-gates ward profile enforces the phase gates AFTER being
# installed, with WARD_RULES_PATH explicitly UNSET — so the result depends ONLY
# on installed profiles (~/.ward/profiles), the previously-broken path.
#
# This is the proof for the profile migration: the foreman-phase Bash DENY here
# happens with NO WARD_RULES_PATH in the environment, which the old wiring could
# never achieve for the `ward eval` hook process.
#
# Uses THROWAWAY session ids only and deletes their state files afterward.
# It does NOT run `ward set` on any live session.

set -u

WARD_BIN="${WARD_BIN:-ward}"
PROFILE_DIR="${PROFILE_DIR:-C:/Users/Q/code/protocols-plugin/plugins/protocols/ward-profile}"

# CRITICAL: results must depend only on installed profiles.
unset WARD_RULES_PATH
unset WARD_SESSION

STATE_DIR="$TEMP/ward"
SID_FOREMAN="wp-verify-foreman-$$"
SID_PLANNING="wp-verify-planning-$$"
SID_EXP="wp-verify-exp-$$"

# Throwaway git repo as cwd (Windows-form path so ward.exe can chdir / see git).
REPO="$(mktemp -d)"
git -C "$REPO" init -q
: > "$REPO/f.txt"
git -C "$REPO" add f.txt >/dev/null 2>&1
git -C "$REPO" -c user.email=t@t -c user.name=t commit -qm init >/dev/null 2>&1
REPO_WIN="$(cygpath -m "$REPO")"

fail=0

cleanup() {
  rm -f "$STATE_DIR/$SID_FOREMAN.json" "$STATE_DIR/$SID_PLANNING.json" "$STATE_DIR/$SID_EXP.json"
  rm -rf "$REPO"
}
trap cleanup EXIT

event() { # tool, command, sid
  printf '{"hook_event_name":"PreToolUse","tool_name":"%s","tool_input":{"command":"%s"},"session_id":"%s","cwd":"%s"}' \
    "$1" "$2" "$3" "$REPO_WIN"
}

run_case() { # desc, tool, command, sid, needle, expect(DENY|ALLOW)
  local desc="$1" tool="$2" cmd="$3" sid="$4" needle="$5" expect="$6" out got
  out="$(event "$tool" "$cmd" "$sid" | "$WARD_BIN" eval -v 2>/dev/null)"
  got="ALLOW"
  if printf '%s' "$out" | grep -qF "$needle"; then got="DENY"; fi
  echo "=== $desc"
  echo "    tool/cmd: $tool $cmd"
  echo "    session : $sid"
  echo "    expected: $expect   got: $got"
  echo "    stdout  : $out"
  if [ "$got" != "$expect" ]; then echo "    RESULT  : MISMATCH"; fail=1; else echo "    RESULT  : OK"; fi
  echo
}

echo "### WARD_RULES_PATH is: '${WARD_RULES_PATH:-<UNSET>}'  (must be UNSET)"
echo

echo "### 1. Install protocols-gates profile from repo"
"$WARD_BIN" install-profile "$PROFILE_DIR"
echo

echo "### ward list-profiles (protocols-gates must appear)"
"$WARD_BIN" list-profiles
echo

echo "### ward validate (compile effective installed ruleset, 0 errors expected)"
"$WARD_BIN" validate
echo

echo "### Set phases on THROWAWAY sessions only (never the live session)"
"$WARD_BIN" set foreman          --session "$SID_FOREMAN"  >/dev/null
"$WARD_BIN" set planning         --session "$SID_PLANNING" >/dev/null
"$WARD_BIN" set experiment-worker --session "$SID_EXP"     >/dev/null
echo

# THE PROOF: foreman-phase Bash denies with WARD_RULES_PATH unset.
run_case "foreman + Bash ls (THE PROOF)" "Bash" "ls" "$SID_FOREMAN" \
  "Foreman protocol active" "DENY"
run_case "planning + Bash ls (phase-scoped, not blanket)" "Bash" "ls" "$SID_PLANNING" \
  "Foreman protocol active" "ALLOW"
run_case "experiment-worker + git push" "Bash" "git push" "$SID_EXP" \
  "Experiment protocol active" "DENY"

if [ "$fail" -eq 0 ]; then
  echo "ALL PROFILE VERIFICATION CASES PASSED"
else
  echo "PROFILE VERIFICATION FAILURE"
fi
exit "$fail"
