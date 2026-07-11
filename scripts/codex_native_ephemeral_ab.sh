#!/usr/bin/env bash
# Controlled Codex 0.144.1 lifecycle reproducer. The only arm variable is
# whether --ephemeral is present. Generated evidence belongs to iteration 005.

set -euo pipefail

if grep -qi microsoft /proc/version 2>/dev/null \
  && [ -x /mnt/c/Users/Q/scoop/apps/git/current/bin/bash.exe ]; then
  script_win="$(wslpath -w "$0")"
  exec /mnt/c/Users/Q/scoop/apps/git/current/bin/bash.exe "$script_win" "$@"
fi

ROOT="${ROOT:-C:/Users/Q/code/protocols-plugin}"
CODEX_BIN="${CODEX_BIN:-codex}"
OUT="$ROOT/reports/iterations/005/ephemeral-ab"
TEMP_WIN="$(cygpath -m "${TEMP:-/tmp}")"
FIXTURE_WIN="$TEMP_WIN/protocols-codex-native-ephemeral-ab"
FIXTURE="$(cygpath -u "$FIXTURE_WIN")"
WARD_ROOT="$(cygpath -u "$TEMP_WIN/ward")"

for command in "$CODEX_BIN" jq rg sha256sum cygpath; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing A/B prerequisite: $command" >&2
    exit 1
  }
done

[ "$($CODEX_BIN --version)" = "codex-cli 0.144.1" ] || {
  echo "A/B requires codex-cli 0.144.1" >&2
  exit 1
}

rm -rf "$OUT"
mkdir -p "$OUT" "$FIXTURE"
printf 'closed\n' >"$FIXTURE/gate-closed"

prompt="Native Codex Ward ephemeral A/B. Use the collaboration spawn tool exactly once with the unselectable default worker type. Tell that worker: report its concrete agent id; repeatedly run only the allowed read-only command rg --files '$FIXTURE_WIN' until that listing contains gate-open; after gate-open appears, return the agent id and stop. Wait for that worker to finish. Do not launch any other worker. Return exactly NATIVE_CODEX_EPHEMERAL_AB followed by the worker report."

run_arm() {
  arm="$1"
  shift
  arm_dir="$OUT/$arm"
  mkdir -p "$arm_dir/ward-live" "$arm_dir/ward-after"
  rm -f "$FIXTURE/gate-open"

  set +e
  "$CODEX_BIN" exec --json "$@" \
    --dangerously-bypass-approvals-and-sandbox \
    -C "$ROOT" "$prompt" >"$arm_dir/stdout.jsonl" 2>"$arm_dir/stderr.txt" &
  codex_pid=$!
  set -e

  root_id=""
  family=""
  gate_opened=false
  for _ in $(seq 1 1200); do
    if [ -z "$root_id" ] && [ -s "$arm_dir/stdout.jsonl" ]; then
      root_id="$(jq -r 'select(.type == "thread.started") | .thread_id' \
        "$arm_dir/stdout.jsonl" 2>/dev/null | head -n1 || true)"
      if [ -n "$root_id" ]; then
        family_hash="$(printf '%s' "$root_id" | sha256sum | awk '{print $1}')"
        family="$WARD_ROOT/families/$family_hash"
      fi
    fi

    if [ -n "$family" ] && [ -d "$family" ]; then
      rm -rf "$arm_dir/ward-live"
      mkdir -p "$arm_dir/ward-live"
      cp -R "$family"/. "$arm_dir/ward-live"/
      if rg -l '"agent_type":"default"' "$family/actors"/*.json 2>/dev/null \
        | xargs -r rg -l '"phase":"codex-scout"' >/dev/null 2>&1; then
        : >"$FIXTURE/gate-open"
        gate_opened=true
      fi
    fi

    if ! kill -0 "$codex_pid" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done

  if kill -0 "$codex_pid" 2>/dev/null; then
    kill "$codex_pid" 2>/dev/null || true
    wait "$codex_pid" 2>/dev/null || true
    codex_exit=124
  else
    set +e
    wait "$codex_pid"
    codex_exit=$?
    set -e
  fi

  family_present_after=false
  if [ -n "$family" ] && [ -d "$family" ]; then
    cp -R "$family"/. "$arm_dir/ward-after"/
    family_present_after=true
  fi

  {
    printf 'arm=%s\n' "$arm"
    printf 'codex_args=%s\n' "$*"
    printf 'codex_exit=%s\n' "$codex_exit"
    printf 'root_thread_id=%s\n' "$root_id"
    printf 'ward_family=%s\n' "$family"
    printf 'gate_opened=%s\n' "$gate_opened"
    printf 'family_present_after=%s\n' "$family_present_after"
  } >"$arm_dir/metadata.txt"
}

run_arm ephemeral --ephemeral
run_arm persistent

rm -rf "$FIXTURE"
echo "A/B evidence: $OUT"
