#!/usr/bin/env bash
# Verify the installed profile against one actor-scoped session family.

set -u

if [ -z "${WARD_BIN:-}" ] && [ -x /mnt/c/Users/Q/go/bin/ward.exe ]; then
  WARD_BIN=/mnt/c/Users/Q/go/bin/ward.exe
else
  WARD_BIN="${WARD_BIN:-ward}"
fi
ROOT="${ROOT:-$PWD}"
PROFILE_DIR="${PROFILE_DIR:-$ROOT/plugins/protocols/ward-profile}"
ROLE_HOOK="$ROOT/plugins/protocols/hooks/ward-role.sh"
SID="wp-actor-family-$$"
SCOUT_ID="scout-$$"
EXP_ID="experiment-$$"
CODEX_ID="native-codex-scout"
UNKNOWN_ID="unknown-$$"
MISSING_ID="missing-$$"
REPO="$(mktemp -d)"
native_path() {
  if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"
  elif command -v wslpath >/dev/null 2>&1; then wslpath -w "$1"
  else printf '%s\n' "$1"
  fi
}
REPO_WIN="$(native_path "$REPO")"
PROFILE_NATIVE="$(native_path "$PROFILE_DIR")"
fail=0

cleanup() {
  jq -cn --arg sid "$SID" '{hook_event_name:"SessionEnd",session_id:$sid}' | "$WARD_BIN" end-session >/dev/null 2>&1 || true
  rm -rf "$REPO"
}
trap cleanup EXIT

git -C "$REPO" init -q
: > "$REPO/f.txt"
git -C "$REPO" add f.txt >/dev/null 2>&1
git -C "$REPO" -c user.email=t@t -c user.name=t commit -qm init >/dev/null 2>&1

event() { # tool, command, agent id, agent type, file path
  jq -cn \
    --arg tool "$1" --arg command "$2" --arg sid "$SID" \
    --arg cwd "$REPO_WIN" --arg agent "$3" --arg type "$4" --arg path "$5" \
    '{hook_event_name:"PreToolUse",tool_name:$tool,
      tool_input:({command:$command} + (if $path == "" then {} else {file_path:$path} end)),
      session_id:$sid,cwd:$cwd}
      + (if $agent == "" then {} else {agent_id:$agent} end)
      + (if $type == "" then {} else {agent_type:$type} end)'
}

start_role() { # agent id, agent type
  jq -cn --arg sid "$SID" --arg agent "$1" --arg type "$2" \
    '{hook_event_name:"SubagentStart",session_id:$sid,agent_id:$agent,agent_type:$type}' |
    CLAUDE_PLUGIN_ROOT="$ROOT/plugins/protocols" WARD_BIN="$WARD_BIN" bash "$ROLE_HOOK" >/dev/null
}

run_case() { # description, tool, command, agent id, agent type, path, expected
  local desc="$1" out got
  out="$(event "$2" "$3" "$4" "$5" "$6" | "$WARD_BIN" eval -v 2>&1)"
  got="ALLOW"
  if printf '%s' "$out" | grep -q 'permissionDecision.*deny'; then got="DENY"; fi
  printf '=== %s\n    expected: %s   got: %s\n' "$desc" "$7" "$got"
  if [ "$got" != "$7" ]; then
    printf '    stdout: %s\n    RESULT: MISMATCH\n' "$out"
    fail=1
  else
    echo "    RESULT: OK"
  fi
}

unset WARD_RULES_PATH WARD_SESSION WARD_ACTOR_ID
"$WARD_BIN" validate-profile "$PROFILE_NATIVE"
"$WARD_BIN" install-profile "$PROFILE_NATIVE"
"$WARD_BIN" validate
"$WARD_BIN" set foreman --session "$SID" >/dev/null

start_role "$SCOUT_ID" protocols:scout
start_role "$EXP_ID" protocols:experiment-worker
if ! start_role "$CODEX_ID" default; then
  echo "native Codex default role failed to initialize"
  fail=1
fi
if start_role "$UNKNOWN_ID" general-purpose 2>/dev/null; then
  echo "unknown role unexpectedly initialized"
  fail=1
fi
if jq -cn --arg sid "$SID" --arg agent "$MISSING_ID" \
    '{hook_event_name:"SubagentStart",session_id:$sid,agent_id:$agent}' |
    CLAUDE_PLUGIN_ROOT="$ROOT/plugins/protocols" WARD_BIN="$WARD_BIN" bash "$ROLE_HOOK" >/dev/null 2>&1; then
  echo "missing role unexpectedly initialized"
  fail=1
fi

run_case "manager Bash denied" Bash "git status" "" "" "" DENY
run_case "manager Edit denied" Edit "" "" "" "$REPO_WIN/source.txt" DENY
run_case "manager non-prompt Write denied" Write "" "" "" "$REPO_WIN/report.md" DENY
run_case "manager Task dispatch allowed" Task "" "" "" "" ALLOW
run_case "manager Codex dispatch allowed" Bash "codex exec review" "" "" "" ALLOW
run_case "scout Bash allowed" Bash "git status" "$SCOUT_ID" protocols:scout "" ALLOW
run_case "scout report Write allowed" Write "" "$SCOUT_ID" protocols:scout "$REPO_WIN/reports/scout.md" ALLOW
run_case "experiment commit allowed" Bash "git commit -m fixture" "$EXP_ID" protocols:experiment-worker "" ALLOW
run_case "experiment promotion denied" Bash "git push" "$EXP_ID" protocols:experiment-worker "" DENY
run_case "experiment evaluator Write denied" Write "" "$EXP_ID" protocols:experiment-worker "$REPO_WIN/tests/gold.txt" DENY
run_case "native Codex rg files allowed" Bash "rg --files" "$CODEX_ID" default "" ALLOW
run_case "native Codex rg search allowed" Bash "rg -n actor plugins" "$CODEX_ID" default "" ALLOW
run_case "native Codex git status allowed" Bash "git status" "$CODEX_ID" default "" ALLOW
run_case "native Codex git diff allowed" Bash "git diff --stat" "$CODEX_ID" default "" ALLOW
run_case "native Codex git log allowed" Bash "git log -1 --oneline" "$CODEX_ID" default "" ALLOW
run_case "native Codex git show allowed" Bash "git show --stat HEAD" "$CODEX_ID" default "" ALLOW
run_case "native Codex git rev-parse allowed" Bash "git rev-parse HEAD" "$CODEX_ID" default "" ALLOW
run_case "native Codex Edit denied" Edit "" "$CODEX_ID" default "$REPO_WIN/source.txt" DENY
run_case "native Codex Write denied" Write "" "$CODEX_ID" default "$REPO_WIN/report.md" DENY
run_case "native Codex Set-Content denied" Bash "Set-Content -Path report.md -Value changed" "$CODEX_ID" default "" DENY
run_case "native Codex git commit denied" Bash "git commit -m forbidden" "$CODEX_ID" default "" DENY
run_case "native Codex arbitrary executable denied" Bash "curl https://example.com" "$CODEX_ID" default "" DENY
run_case "native Codex rg preprocessor denied" Bash "rg --pre 'touch report.md' actor" "$CODEX_ID" default "" DENY
run_case "native Codex shell write denied" Bash "touch report.md" "$CODEX_ID" default "" DENY
run_case "native Codex output redirection denied" Bash "rg --files > report.md" "$CODEX_ID" default "" DENY
run_case "native Codex command substitution denied" Bash 'rg "$(touch report.md)"' "$CODEX_ID" default "" DENY
run_case "uninitialized Bash denied" Bash "git status" "$UNKNOWN_ID" general-purpose "" DENY
run_case "uninitialized Edit denied" Edit "" "$UNKNOWN_ID" general-purpose "$REPO_WIN/source.txt" DENY
run_case "uninitialized Write denied" Write "" "$UNKNOWN_ID" general-purpose "$REPO_WIN/report.md" DENY
run_case "uninitialized native Read allowed" Read "" "$UNKNOWN_ID" general-purpose "$REPO_WIN/prompt.md" ALLOW
run_case "missing type remains uninitialized" Bash "git status" "$MISSING_ID" "" "" DENY

jq -cn --arg sid "$SID" --arg agent "$SCOUT_ID" \
  '{hook_event_name:"SubagentStop",session_id:$sid,agent_id:$agent}' | "$WARD_BIN" end-actor >/dev/null
run_case "manager remains foreman after scout stop" Bash "git status" "" "" "" DENY
run_case "experiment survives scout stop" Bash "git push" "$EXP_ID" protocols:experiment-worker "" DENY

jq -cn --arg sid "$SID" --arg agent "$EXP_ID" \
  '{hook_event_name:"SubagentStop",session_id:$sid,agent_id:$agent}' | "$WARD_BIN" end-actor >/dev/null
run_case "manager remains foreman after all workers stop" Bash "git status" "" "" "" DENY

if [ "$fail" -eq 0 ]; then
  echo "ALL ACTOR-SCOPED PROFILE CASES PASSED"
else
  echo "ACTOR-SCOPED PROFILE FAILURE"
fi
exit "$fail"
