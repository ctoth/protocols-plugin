#!/bin/bash
# SubagentStart hook: map an explicit Claude agent_type to its Ward actor phase.

set -euo pipefail

if [ -z "${WARD_BIN:-}" ] && command -v ward.exe >/dev/null 2>&1; then
    WARD_BIN=ward.exe
else
    WARD_BIN="${WARD_BIN:-ward}"
fi

command -v "$WARD_BIN" >/dev/null 2>&1 || {
    echo "protocols: Ward is required for Task role initialization" >&2
    exit 1
}
command -v jq >/dev/null 2>&1 || {
    echo "protocols: jq is required for Task role initialization" >&2
    exit 1
}

input="$(cat)"
agent_type="$(printf '%s' "$input" | jq -er '.agent_type | select(type == "string" and length > 0)' 2>/dev/null || true)"

case "$agent_type" in
    scout|coder|analyst|verifier|researcher|adversary|experiment-worker)
        phase="$agent_type"
        ;;
    *)
        # Preserve Ward's fail-closed actor record even when the launch used an
        # unknown or generic Task type. The launcher must select a supported role.
        printf '%s' "$input" | "$WARD_BIN" start-actor
        echo "protocols: unsupported agent_type '${agent_type:-<missing>}'; actor remains uninitialized" >&2
        exit 1
        ;;
esac

printf '%s' "$input" | "$WARD_BIN" set "$phase" --hook-input
