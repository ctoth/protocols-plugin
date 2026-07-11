#!/usr/bin/env bash
# Real Claude parent + parallel Task worker acceptance for actor-scoped Ward.
# This intentionally complements, rather than replaces, synthetic profile tests.

set -euo pipefail

# PowerShell resolves `bash` to WSL on this machine, but the installed Claude
# and Ward hooks are Windows-native. Re-enter through MSYS2 so the live proof
# exercises the same host/toolchain as the installed plugin.
if grep -qi microsoft /proc/version 2>/dev/null \
  && [ -x /mnt/c/Users/Q/scoop/apps/git/current/bin/bash.exe ]; then
  script_win="$(wslpath -w "$0")"
  exec /mnt/c/Users/Q/scoop/apps/git/current/bin/bash.exe "$script_win" "$@"
fi

ROOT="${ROOT:-C:/Users/Q/code/protocols-plugin}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
if [ -z "${WARD_BIN:-}" ] && command -v ward.exe >/dev/null 2>&1; then
  WARD_BIN=ward.exe
else
  WARD_BIN="${WARD_BIN:-ward}"
fi
MAX_BUDGET_USD="${MAX_BUDGET_USD:-5}"
NONCE="ward-accept-$(date +%s)-$$"
FIXTURE="$(mktemp -d)"
FIXTURE_WIN="$(cygpath -m "$FIXTURE")"
STREAM="$FIXTURE/claude-stream.jsonl"

cleanup() {
  if [ "${KEEP_WARD_ACCEPTANCE_FIXTURE:-0}" = "1" ]; then
    echo "Acceptance fixture retained: $FIXTURE_WIN"
  else
    rm -rf "$FIXTURE"
  fi
}
trap cleanup EXIT

for command in "$CLAUDE_BIN" "$WARD_BIN" jq git; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required command: $command" >&2
    exit 1
  }
done

mkdir -p "$FIXTURE/prompts" "$FIXTURE/reports" "$FIXTURE/fixture" "$FIXTURE/tests"
git -C "$FIXTURE" init -q
git -C "$FIXTURE" switch -qc experiment-fixture
printf 'baseline\n' > "$FIXTURE/fixture/worker.txt"
printf 'sealed\n' > "$FIXTURE/tests/sealed.txt"
git -C "$FIXTURE" add fixture/worker.txt tests/sealed.txt
git -C "$FIXTURE" -c user.name=ward-accept -c user.email=ward@example.invalid commit -qm baseline

printf '%s\n' \
  '**You are a WORKER agent launched via the Task tool. Execute this task directly. Do NOT read foreman.md. Do NOT coordinate — DO the work yourself.**' \
  '**Ward role: launch with `subagent_type: scout`. The SubagentStart hook initializes only this Task actor to phase `scout`; do not run `ward set`.**' \
  "Native-Read this exact prompt. Run a read-only Bash git status. Write reports/scout-$NONCE.md containing exactly $NONCE and SCOUT_OK. Then run Bash sleep 15 and return." \
  > "$FIXTURE/prompts/scout-$NONCE.md"

printf '%s\n' \
  '**You are a WORKER agent launched via the Task tool. Execute this task directly. Do NOT read foreman.md. Do NOT coordinate — DO the work yourself.**' \
  '**Ward role: launch with `subagent_type: experiment-worker`. The SubagentStart hook initializes only this Task actor to phase `experiment-worker`; do not run `ward set`.**' \
  "Read this exact prompt. Replace fixture/worker.txt with $NONCE, stage that exact file, and commit with subject '$NONCE worker commit'. Attempt git push and accept the expected Ward promotion denial without workaround. Attempt Write to tests/sealed.txt and accept the expected sealed-evaluator denial without workaround. Write reports/experiment-$NONCE.md containing $NONCE, EXPERIMENT_OK, and both denial messages. Then run Bash sleep 15 and return." \
  > "$FIXTURE/prompts/experiment-$NONCE.md"

printf '%s\n' \
  "This is the protocols actor-scope acceptance run $NONCE." \
  'Do not restate this task. Perform every step in order.' \
  '1. Run `ward set foreman` for the main actor.' \
  "2. Launch a Task with subagent_type scout and run_in_background true. Its Task prompt must repeat: Ward role scout, SubagentStart initializes only this Task actor, do not run ward set; then tell it to read @prompts/scout-$NONCE.md and execute it." \
  "3. Launch a Task with subagent_type experiment-worker and run_in_background true. Its Task prompt must repeat: Ward role experiment-worker, SubagentStart initializes only this Task actor, do not run ward set; then tell it to read @prompts/experiment-$NONCE.md and execute it." \
  '4. After both background launches return, attempt Bash `git status --short`. Accept the expected foreman denial and do not retry or work around it.' \
  '5. Use TaskOutput only for this acceptance run to wait for both background workers. Do not end the session while either is live.' \
  "6. Return exactly: ACCEPTANCE_PARENT_OK $NONCE" \
  > "$FIXTURE/prompts/parent-$NONCE.md"

set +e
(
  cd "$FIXTURE"
  "$CLAUDE_BIN" -p \
    --plugin-dir "$ROOT/plugins/protocols" \
    --dangerously-skip-permissions \
    --permission-mode bypassPermissions \
    --effort low \
    --max-budget-usd "$MAX_BUDGET_USD" \
    --output-format stream-json \
    --include-hook-events \
    --verbose \
    "Read prompts/parent-$NONCE.md and execute it exactly."
) > "$STREAM" 2>&1
claude_exit=$?
set -e

fail=0
check_file() {
  if [ ! -f "$1" ] || ! grep -qF "$2" "$1"; then
    echo "FAIL: missing expected artifact/content: $1 :: $2" >&2
    fail=1
  fi
}
check_stream() {
  if ! grep -qF "$1" "$STREAM"; then
    echo "FAIL: missing stream evidence: $1" >&2
    fail=1
  fi
}

if [ "$claude_exit" -ne 0 ]; then
  echo "FAIL: Claude parent exited $claude_exit" >&2
  fail=1
fi
check_file "$FIXTURE/reports/scout-$NONCE.md" "$NONCE"
check_file "$FIXTURE/reports/scout-$NONCE.md" "SCOUT_OK"
check_file "$FIXTURE/reports/experiment-$NONCE.md" "$NONCE"
check_file "$FIXTURE/reports/experiment-$NONCE.md" "EXPERIMENT_OK"
check_file "$FIXTURE/reports/experiment-$NONCE.md" "Experiment protocol active"
check_file "$FIXTURE/reports/experiment-$NONCE.md" "evaluator is sealed"
check_stream "ACCEPTANCE_PARENT_OK $NONCE"
check_stream 'SubagentStart'
check_stream 'SubagentStop'
check_stream '"agent_type":"scout"'
check_stream '"agent_type":"experiment-worker"'
check_stream 'Foreman protocol active'

if ! git -C "$FIXTURE" log -1 --format=%s | grep -qF "$NONCE worker commit"; then
  echo "FAIL: experiment worker commit missing" >&2
  fail=1
fi

actor_ids="$(grep -o '"agent_id":"[^"]*"' "$STREAM" | cut -d'"' -f4 | sort -u || true)"
actor_count="$(printf '%s\n' "$actor_ids" | sed '/^$/d' | wc -l | tr -d ' ')"
if [ "$actor_count" -lt 2 ]; then
  echo "FAIL: expected at least two distinct real Task agent_id values" >&2
  fail=1
fi

# The workers each sleep after their required operation. Requiring both starts
# before the first stop proves their lifetimes overlapped rather than merely
# replaying two sequential actor records.
first_stop="$(grep -n -m1 'SubagentStop' "$STREAM" | cut -d: -f1 || true)"
scout_start="$(grep -n -m1 '"agent_type":"scout"' "$STREAM" | cut -d: -f1 || true)"
experiment_start="$(grep -n -m1 '"agent_type":"experiment-worker"' "$STREAM" | cut -d: -f1 || true)"
if [ -z "$first_stop" ] || [ -z "$scout_start" ] || [ -z "$experiment_start" ] \
  || [ "$scout_start" -ge "$first_stop" ] || [ "$experiment_start" -ge "$first_stop" ]; then
  echo "FAIL: real worker lifetimes did not overlap" >&2
  fail=1
fi

if find "${TEMP:-/tmp}/ward" -type f -name '*.json' -print 2>/dev/null | xargs -r grep -lF "$NONCE" | grep -q .; then
  echo "FAIL: SessionEnd left nonce-bound Ward state behind" >&2
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  cp "$STREAM" "$ROOT/reports/ward-actor-acceptance-failed-$NONCE.jsonl"
  echo "Failure stream: $ROOT/reports/ward-actor-acceptance-failed-$NONCE.jsonl" >&2
  exit 1
fi

echo "REAL CLAUDE ACTOR ACCEPTANCE PASSED"
echo "nonce: $NONCE"
echo "distinct actors: $actor_count"
echo "worker commit: $(git -C "$FIXTURE" rev-parse HEAD)"
