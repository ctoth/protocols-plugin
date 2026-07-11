#!/bin/bash
# SessionStart hook: install/update the protocols-gates ward profile.
#
# The phase gates (foreman/adversary/researcher/experiment) must load for the
# `ward eval` PreToolUse hook process. That process is spawned directly by
# Claude Code and never sees WARD_RULES_PATH (Claude injects $CLAUDE_ENV_FILE
# vars into the Bash tool as NON-exported shell variables only), so the old
# WARD_RULES_PATH wiring left the gates inert. Installing them as a ward
# profile puts the rules in ~/.ward/profiles/, which ward loads for every
# session regardless of environment — exactly how core-safety loads.
#
# Idempotent and fail-closed: an absent/incompatible Ward or a profile install
# failure is surfaced to SessionStart instead of silently disabling enforcement.

set -euo pipefail

PROFILE_DIR="${CLAUDE_PLUGIN_ROOT}/ward-profile"
if [ -z "${WARD_BIN:-}" ] && command -v ward.exe >/dev/null 2>&1; then
    WARD_BIN=ward.exe
else
    WARD_BIN="${WARD_BIN:-ward}"
fi

command -v "$WARD_BIN" >/dev/null 2>&1 || {
    echo "protocols: Ward is required but was not found" >&2
    exit 1
}
[ -f "$PROFILE_DIR/profile.yaml" ] || {
    echo "protocols: missing bundled Ward profile: $PROFILE_DIR/profile.yaml" >&2
    exit 1
}

"$WARD_BIN" start-actor --help 2>&1 | grep -q "uninitialized phase" || {
    echo "protocols: installed Ward lacks actor-scoped SubagentStart support" >&2
    exit 1
}
"$WARD_BIN" set --help 2>&1 | grep -q -- "--hook-input" || {
    echo "protocols: installed Ward lacks actor-scoped hook initialization" >&2
    exit 1
}

"$WARD_BIN" validate-profile "$PROFILE_DIR" >/dev/null

want="$(grep -m1 '^version:' "$PROFILE_DIR/profile.yaml" | awk '{print $2}')"
have="$("$WARD_BIN" list-profiles 2>/dev/null | awk -F'\t' '$1=="protocols-gates"{print $2}')"

if [ "$want" != "$have" ]; then
    "$WARD_BIN" install-profile "$PROFILE_DIR" >/dev/null
fi

installed="$("$WARD_BIN" list-profiles | awk -F'\t' '$1=="protocols-gates"{print $2}')"
[ "$installed" = "$want" ] || {
    echo "protocols: Ward profile version mismatch (want $want, have ${installed:-missing})" >&2
    exit 1
}
"$WARD_BIN" validate >/dev/null
