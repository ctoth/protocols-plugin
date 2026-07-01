# protocols-plugin

Agent behavioral protocols for Claude Code, Codex CLI, and Gemini CLI, with mechanical tool restriction enforcement via [ward](https://github.com/ctoth/ward) where supported.

## What This Does

Provides 13 behavioral protocol skills that define operational modes for Claude Code, Codex CLI, and Gemini CLI agents. Each protocol constrains agent behavior — what tools are available, what workflow to follow, what the agent's role is.

Protocols that restrict tools (foreman, adversary, researcher, experiment) include ward gate rules that mechanically enforce those restrictions at the PreToolUse hook level, preventing accidental violations.

Codex and Gemini do not use Claude's plugin marketplace, so this repository also
ships a script-based installer that links the protocol skill directories into
their user skill roots.

## Protocols

| Protocol | Description |
|----------|-------------|
| **foreman** | Coordination only — dispatch subagents, do not execute code |
| **subagent** | How to write and launch subagent prompts (auto-invocable) |
| **gauntlet** | Scout -> Coder -> Analyst -> Verifier pipeline for high-risk changes |
| **investigation** | Structured debugging with competing hypotheses and escalation levels |
| **experiment** | Controlled benchmark experiments with baseline, gates, records, and promote/abandon decisions |
| **phases** | Parallel/sequential workflow phases with filesystem-based coordination |
| **iterations** | Tracked iteration cycles for reducing failures with regression detection |
| **cleanup-refactor** | Deletion-first fixed-point cleanup for refactors, migrations, helper removal, and ownership repair |
| **adversary** | Read-only design review against project principles |
| **researcher** | Pre-implementation research with web access |
| **external-agents** | Using Codex/Gemini CLIs as external reviewers |
| **spec-updating** | Spec update workflow with discovery, draft, and review gates |
| **RE** | Reverse engineering — documentation is the work product |

## Agents

The plugin ships the four gauntlet roles as **Claude-native** tool-scoped agents in
`plugins/protocols/agents/`. Dispatch them via the Task tool with
`subagent_type: scout` / `coder` / `analyst` / `verifier`. Their tool restriction is
enforced by the agent frontmatter itself (`tools` / `disallowedTools`), independent of ward.

| Agent | `subagent_type` | Tools | Role |
|-------|-----------------|-------|------|
| **scout** | `scout` | Read, Glob, Grep, Bash, Write (no Edit) | Survey the codebase, cite `file:line`, do not implement |
| **coder** | `coder` | Read, Glob, Grep, Bash, Edit, Write | Implement the plan with full TDD; commit own work |
| **analyst** | `analyst` | Read, Glob, Grep, Bash, Write (no Edit) | Find problems — edge cases, security, races; do not fix |
| **verifier** | `verifier` | Read, Glob, Grep, Bash, Write (no Edit) | Gate the merge; default NO-MERGE |

These agents are Claude-only. Codex and Gemini do not load Claude plugin agents — they
consume the equivalent doctrine from the `gauntlet` and `subagent` skills' prose.

The script-based installer (`scripts/install_skills.py`) installs **skills only**. Agents
load through Claude's native plugin system: the `agents/` directory is auto-discovered when
the plugin is installed via `claude plugin install`, so no manifest declaration is required.

## Ward Integration

Protocols that restrict tools use [ward](https://github.com/ctoth/ward) for mechanical enforcement:

1. **SessionStart hook** installs/updates this plugin's `protocols-gates` ward profile (from `plugins/protocols/ward-profile/`) into `~/.ward/profiles/`, so the gates load for the `ward eval` hook on every session — independent of environment
2. When a protocol is activated (e.g., `ward set foreman`), ward's `session.phase` is set
3. Ward gate rules fire on every tool call, denying tools that the protocol forbids

### Gate Rules

| Rule | Phase | Denies |
|------|-------|--------|
| `foreman-gate.yaml` | `foreman` | Bash, Edit, Write (except prompts/ and notes-*) |
| `adversary-gate.yaml` | `adversary` | Edit, Write, Bash |
| `researcher-gate.yaml` | `researcher` | Edit (Write allowed for reports) |
| `experiment-gate.yaml` | `experiment-worker` | Integration-branch moves — `git push`, `merge`, `rebase`, `cherry-pick`, `pull`, `switch`/`checkout` (commit, add, branch, tag stay allowed; override: `ward allow experiment-promote`) |

## Installation

### Claude plugin install

```bash
claude plugin marketplace add ctoth/protocols-plugin
claude plugin install protocols@protocols-marketplace
```

### Script-based installer for Codex and Gemini

Use the bundled installer when you want the protocol skills installed into
Codex and/or Gemini user skill directories:

```bash
uv run scripts/install_skills.py doctor
uv run scripts/install_skills.py install --platform codex --platform gemini
```

What the installer does:

- discovers every `plugins/*/skills/*/SKILL.md` directory;
- installs Codex skills into both `~/.agents/skills` and
  `~/.codex/skills/protocols-plugin`;
- installs Gemini skills into `~/.gemini/skills`;
- uses symlinks when possible and managed copies when symlinks are unavailable;
- refuses to overwrite unmanaged destinations unless `--force` is supplied.

Common commands:

```bash
uv run scripts/install_skills.py install
uv run scripts/install_skills.py install --platform codex
uv run scripts/install_skills.py install --platform gemini
uv run scripts/install_skills.py install --platform claude
uv run scripts/install_skills.py uninstall
```

`install --platform claude` uses Claude's native `claude plugin
marketplace add/install` flow under the hood. Omitting `--platform` installs all
supported targets.

## Requirements

- [ward](https://github.com/ctoth/ward) must be installed and configured as a PreToolUse hook
- Ward must support installable profiles (`ward install-profile`); the SessionStart hook installs the `protocols-gates` profile
- `uv` is required for the script-based installer

## Usage

Activate a protocol by invoking it as a skill:

```
/protocols:foreman      # Enter foreman coordination mode
/protocols:gauntlet     # Start a scout->coder->analyst->verifier pipeline
/protocols:investigation # Begin structured debugging
/protocols:experiment   # Run a controlled benchmark experiment
/protocols:cleanup-refactor # Run deletion-first fixed-point cleanup
/protocols:adversary    # Run read-only principle alignment check
/protocols:researcher   # Enter research mode with web access
```

The `subagent` protocol is auto-invocable — it provides background knowledge whenever you dispatch agents.

Protocols that restrict tools will instruct you to run `ward set <protocol>` to activate mechanical enforcement.

## License

MIT
