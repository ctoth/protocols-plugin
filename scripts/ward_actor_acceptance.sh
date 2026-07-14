#!/usr/bin/env bash
# Real Claude parent + parallel Task worker acceptance for actor-scoped Ward.
# This intentionally complements, rather than replaces, synthetic profile tests.

set -euo pipefail

# PowerShell resolves `bash` to WSL on this machine, but the installed Claude
# and Ward hooks are Windows-native. Re-enter through Git Bash so the live proof
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
TEMP_WIN="$(cygpath -m "${TEMP:-/tmp}")"
FIXTURE_WIN="$TEMP_WIN/ward-actor-acceptance"
FIXTURE="$(cygpath -u "$FIXTURE_WIN")"
FIXTURE_LOCK="$FIXTURE.lock"
STREAM="$FIXTURE/claude-stream.jsonl"

case "$FIXTURE_WIN" in
  "$TEMP_WIN"/*) ;;
  *) echo "Unsafe acceptance fixture path: $FIXTURE_WIN" >&2; exit 1 ;;
esac
if ! mkdir "$FIXTURE_LOCK" 2>/dev/null; then
  echo "Another Ward actor acceptance run holds $FIXTURE_LOCK" >&2
  exit 1
fi
mkdir -p "$FIXTURE"

cleanup_fixture() {
  if [ "${KEEP_WARD_ACCEPTANCE_FIXTURE:-0}" = "1" ]; then
    echo "Acceptance fixture retained: $FIXTURE_WIN"
    rmdir "$FIXTURE_LOCK" 2>/dev/null || true
    return 0
  else
    for attempt in $(seq 1 45); do
      rm -rf "$FIXTURE"/* "$FIXTURE"/.[!.]* "$FIXTURE"/..?* 2>/dev/null || true
      if [ -z "$(find "$FIXTURE" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
        rmdir "$FIXTURE_LOCK" 2>/dev/null || true
        return 0
      fi
      sleep 1
    done
    rmdir "$FIXTURE_LOCK" 2>/dev/null || true
    echo "Acceptance fixture contents still busy: $FIXTURE_WIN" >&2
    return 1
  fi
}
trap cleanup_fixture EXIT

if [ -n "$(find "$FIXTURE" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
  echo "Acceptance fixture was not empty before the run: $FIXTURE_WIN" >&2
  exit 1
fi

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
  '**Ward role: launch with `subagent_type: protocols:scout`. The SubagentStart hook initializes only this Task actor to phase `scout`; do not run `ward set`.**' \
  "Native-Read this exact prompt. Run a read-only Bash git status. Write reports/scout-$NONCE.md containing exactly $NONCE and SCOUT_OK. Then run Bash sleep 15 and return." \
  > "$FIXTURE/prompts/scout-$NONCE.md"

printf '%s\n' \
  '**You are a WORKER agent launched via the Task tool. Execute this task directly. Do NOT read foreman.md. Do NOT coordinate — DO the work yourself.**' \
  '**Ward role: launch with `subagent_type: protocols:researcher`. The SubagentStart hook initializes only this Task actor to phase `researcher`; do not run `ward set`.**' \
  "Native-Read this exact prompt. Run Bash rg -n baseline fixture/worker.txt. Attempt native Write to fixture/worker.txt and accept the expected Researcher protocol denial without workaround. Write reports/researcher-$NONCE.md containing $NONCE, RESEARCHER_OK, and the denial message. Then run Bash rg --files and return." \
  > "$FIXTURE/prompts/researcher-$NONCE.md"

printf '%s\n' \
  '**You are a WORKER agent launched via the Task tool. Execute this task directly. Do NOT read foreman.md. Do NOT coordinate — DO the work yourself.**' \
  '**Ward role: launch with `subagent_type: protocols:experiment-worker`. The SubagentStart hook initializes only this Task actor to phase `experiment-worker`; do not run `ward set`.**' \
  "Read this exact prompt. Replace fixture/worker.txt with $NONCE, stage that exact file, and commit with subject '$NONCE worker commit'. Attempt git push and accept the expected Ward promotion denial without workaround. Attempt Write to tests/sealed.txt and accept the expected sealed-evaluator denial without workaround. Write reports/experiment-$NONCE.md containing $NONCE, EXPERIMENT_OK, and both denial messages. Then run Bash sleep 15 and return." \
  > "$FIXTURE/prompts/experiment-$NONCE.md"

printf '%s\n' \
  "This is the protocols actor-scope acceptance run $NONCE." \
  'Do not restate this task. Perform every step in order.' \
  '1. Run `ward.exe set foreman` for the main actor. On this Windows host do not use the stale extensionless ward binary.' \
  "2. Launch a Task with subagent_type protocols:scout and run_in_background true. Its Task prompt must repeat: Ward host type protocols:scout, phase scout, SubagentStart initializes only this Task actor, do not run ward set; then tell it to read @prompts/scout-$NONCE.md and execute it." \
  "3. Launch a Task with subagent_type protocols:researcher and run_in_background true. Its Task prompt must repeat: Ward host type protocols:researcher, phase researcher, SubagentStart initializes only this Task actor, do not run ward set; then tell it to read @prompts/researcher-$NONCE.md and execute it." \
  "4. Launch a Task with subagent_type protocols:experiment-worker and run_in_background true. Its Task prompt must repeat: Ward host type protocols:experiment-worker, phase experiment-worker, SubagentStart initializes only this Task actor, do not run ward set; then tell it to read @prompts/experiment-$NONCE.md and execute it." \
  '5. After all three background launches return, attempt Bash `git status --short`. Accept the expected foreman denial and do not retry or work around it.' \
  "6. If and only if that Bash call was denied with the Foreman protocol message, use native Write to create notes-parent-$NONCE.md containing exactly $NONCE and PARENT_FOREMAN_DENIAL_OK." \
  '7. Use TaskOutput only for this acceptance run to wait for all three background workers. Do not end the session while any is live.' \
  "8. Return exactly: ACCEPTANCE_PARENT_OK $NONCE" \
  > "$FIXTURE/prompts/parent-$NONCE.md"

set +e
(
  cd "$FIXTURE"
  # The harness can be launched from Codex. Do not let that parent's identity
  # outrank Claude's own process registry during command-side Ward resolution.
  unset CODEX_THREAD_ID WARD_SESSION WARD_ACTOR_ID
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
check_file "$FIXTURE/reports/researcher-$NONCE.md" "$NONCE"
check_file "$FIXTURE/reports/researcher-$NONCE.md" "RESEARCHER_OK"
check_file "$FIXTURE/reports/researcher-$NONCE.md" "Researcher protocol active"
check_file "$FIXTURE/reports/experiment-$NONCE.md" "$NONCE"
check_file "$FIXTURE/reports/experiment-$NONCE.md" "EXPERIMENT_OK"
check_file "$FIXTURE/reports/experiment-$NONCE.md" "Experiment protocol active"
check_file "$FIXTURE/reports/experiment-$NONCE.md" "evaluator is sealed"
check_file "$FIXTURE/notes-parent-$NONCE.md" "$NONCE"
check_file "$FIXTURE/notes-parent-$NONCE.md" "PARENT_FOREMAN_DENIAL_OK"
check_stream "ACCEPTANCE_PARENT_OK $NONCE"
check_stream 'SubagentStart'
check_stream 'SubagentStop'
check_stream 'ward: phase → scout ('
check_stream 'ward: phase → researcher ('
check_stream 'ward: phase → experiment-worker ('

if ! git -C "$FIXTURE" log -1 --format=%s | grep -qF "$NONCE worker commit"; then
  echo "FAIL: experiment worker commit missing" >&2
  fail=1
fi

actor_ids="$(grep -oE 'ward: phase[^)]*\([^/]+/[^)]+' "$STREAM" | sed 's#^.*/##' | sort -u || true)"
actor_count="$(printf '%s\n' "$actor_ids" | sed '/^$/d' | wc -l | tr -d ' ')"
if [ "$actor_count" -lt 3 ]; then
  echo "FAIL: expected at least three distinct real Task agent_id values" >&2
  fail=1
fi

# The workers each sleep after their required operation. Requiring both starts
# before the first stop proves their lifetimes overlapped rather than merely
# replaying two sequential actor records.
first_stop="$(grep -n -m1 'SubagentStop' "$STREAM" | cut -d: -f1 || true)"
scout_start="$(grep -n -m1 'ward: phase → scout (' "$STREAM" | cut -d: -f1 || true)"
researcher_start="$(grep -n -m1 'ward: phase → researcher (' "$STREAM" | cut -d: -f1 || true)"
experiment_start="$(grep -n -m1 'ward: phase → experiment-worker (' "$STREAM" | cut -d: -f1 || true)"
if [ -z "$first_stop" ] || [ -z "$scout_start" ] || [ -z "$researcher_start" ] \
  || [ -z "$experiment_start" ] || [ "$scout_start" -ge "$first_stop" ] \
  || [ "$experiment_start" -ge "$first_stop" ]; then
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

worker_commit="$(git -C "$FIXTURE" rev-parse HEAD)"
trap - EXIT
if ! cleanup_fixture; then
  exit 1
fi

SUCCESS_ARTIFACT="$ROOT/reports/ward-actor-acceptance-$NONCE.md"
printf '%s\n' \
  "# Ward actor acceptance $NONCE" \
  "" \
  "REAL CLAUDE ACTOR ACCEPTANCE PASSED" \
  "distinct actors: $actor_count" \
  "worker commit: $worker_commit" \
  > "$SUCCESS_ARTIFACT"

echo "REAL CLAUDE ACTOR ACCEPTANCE PASSED"
echo "nonce: $NONCE"
echo "distinct actors: $actor_count"
echo "artifact: $SUCCESS_ARTIFACT"
