#!/bin/bash
# SubagentStart hook: map exact host agent types to Ward actor phases.

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
# Hosts have shipped this field under more than one name; accept the known
# spellings so a rename does not silently drop every worker into fail-closed.
agent_type="$(printf '%s' "$input" | jq -er '(.agent_type // .subagent_type // .agentType) | select(type == "string" and length > 0)' 2>/dev/null || true)"
codex_turn_id="$(printf '%s' "$input" | jq -er '.turn_id | select(type == "string" and length > 0)' 2>/dev/null || true)"

if [ -z "$agent_type" ] && [ -n "$codex_turn_id" ]; then
    # Codex 0.144.1 defines turn_id as a required Codex extension on this
    # lifecycle payload. Claude Task does not send it, so missing Claude types
    # still take the fail-closed branch below.
    phase=codex-scout
else
    case "$agent_type" in
        scout|protocols:scout) phase=scout ;;
        coder|protocols:coder) phase=coder ;;
        analyst|protocols:analyst) phase=analyst ;;
        verifier|protocols:verifier) phase=verifier ;;
        researcher|protocols:researcher) phase=researcher ;;
        adversary|protocols:adversary) phase=adversary ;;
        experiment-worker|protocols:experiment-worker) phase=experiment-worker ;;
        # A delegated foreman gets the foreman gate, same as a main-session foreman.
        foreman|protocols:foreman) phase=foreman ;;
        # Host built-in read-write worker types: full-capability phase (no gate),
        # same standing as coder/scout. Their own agent tool lists still apply.
        general-purpose|claude|investigator) phase=worker ;;
        # Host built-in read-only/discovery types: discovery-only phase.
        Explore|Plan|claude-code-guide) phase=codex-scout ;;
        # Native Codex collaboration may expose this exact, unselectable sentinel.
        # It receives a distinct discovery-only phase; this does not infer a
        # protocol role from the worker's prompt or agent ID.
        default) phase=codex-scout ;;
        *)
            # Preserve Ward's fail-closed actor record even when the launch used an
            # unknown or generic Task type. The launcher must select a supported role.
            printf '%s' "$input" | "$WARD_BIN" start-actor
            echo "protocols: unsupported agent_type '${agent_type:-<missing>}'; actor remains uninitialized" >&2
            exit 1
            ;;
    esac
fi

printf '%s' "$input" | "$WARD_BIN" set "$phase" --hook-input
