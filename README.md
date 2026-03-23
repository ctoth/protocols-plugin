# protocols-plugin

Agent behavioral protocols for Claude Code, with mechanical tool restriction enforcement via [ward](https://github.com/ctoth/ward).

## What This Does

Provides 11 behavioral protocol skills that define operational modes for Claude Code agents. Each protocol constrains agent behavior — what tools are available, what workflow to follow, what the agent's role is.

Protocols that restrict tools (foreman, adversary, researcher) include ward gate rules that mechanically enforce those restrictions at the PreToolUse hook level, preventing accidental violations.

## Protocols

| Protocol | Description |
|----------|-------------|
| **foreman** | Coordination only — dispatch subagents, do not execute code |
| **subagent** | How to write and launch subagent prompts (auto-invocable) |
| **gauntlet** | Scout -> Coder -> Analyst -> Verifier pipeline for high-risk changes |
| **investigation** | Structured debugging with competing hypotheses and escalation levels |
| **phases** | Parallel/sequential workflow phases with filesystem-based coordination |
| **iterations** | Tracked iteration cycles for reducing failures with regression detection |
| **adversary** | Read-only design review against project principles |
| **researcher** | Pre-implementation research with web access |
| **external-agents** | Using Codex/Gemini CLIs as external reviewers |
| **spec-updating** | Spec update workflow with discovery, draft, and review gates |
| **RE** | Reverse engineering — documentation is the work product |

## Ward Integration

Protocols that restrict tools use [ward](https://github.com/ctoth/ward) for mechanical enforcement:

1. **SessionStart hook** automatically registers this plugin's `ward-rules/` directory via `WARD_RULES_PATH`
2. When a protocol is activated (e.g., `ward set foreman`), ward's `session.phase` is set
3. Ward gate rules fire on every tool call, denying tools that the protocol forbids

### Gate Rules

| Rule | Phase | Denies |
|------|-------|--------|
| `foreman-gate.yaml` | `foreman` | Bash, Edit, Write (except prompts/ and notes-*) |
| `adversary-gate.yaml` | `adversary` | Edit, Write, Bash |
| `researcher-gate.yaml` | `researcher` | Edit (Write allowed for reports) |

## Installation

```bash
claude plugin marketplace add ctoth/protocols-plugin
claude plugin install protocols@protocols-marketplace
```

## Requirements

- [ward](https://github.com/ctoth/ward) must be installed and configured as a PreToolUse hook
- Ward must support `WARD_RULES_PATH` for loading rules from plugin directories

## Usage

Activate a protocol by invoking it as a skill:

```
/protocols:foreman      # Enter foreman coordination mode
/protocols:gauntlet     # Start a scout->coder->analyst->verifier pipeline
/protocols:investigation # Begin structured debugging
/protocols:adversary    # Run read-only principle alignment check
/protocols:researcher   # Enter research mode with web access
```

The `subagent` protocol is auto-invocable — it provides background knowledge whenever you dispatch agents.

Protocols that restrict tools will instruct you to run `ward set <protocol>` to activate mechanical enforcement.

## License

MIT
