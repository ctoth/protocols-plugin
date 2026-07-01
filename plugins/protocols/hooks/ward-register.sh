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
# Idempotent and fast: it only reinstalls when the bundled version differs from
# the installed one (a local-dir copy of a handful of small YAML files), and it
# never fails the hook if ward is missing.

PROFILE_DIR="${CLAUDE_PLUGIN_ROOT}/ward-profile"

# ward not installed → no-op, do not fail the hook.
command -v ward >/dev/null 2>&1 || exit 0
[ -f "$PROFILE_DIR/profile.yaml" ] || exit 0

want="$(grep -m1 '^version:' "$PROFILE_DIR/profile.yaml" | awk '{print $2}')"
have="$(ward list-profiles 2>/dev/null | awk -F'\t' '$1=="protocols-gates"{print $2}')"

if [ "$want" != "$have" ]; then
    ward install-profile "$PROFILE_DIR" >/dev/null 2>&1 || true
fi

exit 0
