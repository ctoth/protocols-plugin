#!/bin/bash
PLUGIN_RULES="${CLAUDE_PLUGIN_ROOT}/ward-rules"
if [ -d "$PLUGIN_RULES" ] && [ -n "$CLAUDE_ENV_FILE" ]; then
    echo "WARD_RULES_PATH=${WARD_RULES_PATH:+${WARD_RULES_PATH}:}${PLUGIN_RULES}" >> "$CLAUDE_ENV_FILE"
fi
