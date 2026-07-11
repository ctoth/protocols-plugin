# protocols-plugin

Agent behavioral protocols for Claude Code, Codex CLI, and Gemini CLI, with mechanical tool restriction enforcement via [ward](https://github.com/ctoth/ward) where supported.

## What This Does

Provides 14 behavioral protocol skills that define operational modes for Claude Code, Codex CLI, and Gemini CLI agents. Each protocol constrains agent behavior — what tools are available, what workflow to follow, what the agent's role is.

Protocols that restrict tools (foreman, adversary, researcher, experiment) include ward gate rules that mechanically enforce those restrictions at the PreToolUse hook level, preventing accidental violations.

Codex uses its own native plugin installation and cache, while Gemini consumes
skill directories directly. This repository ships one installer that manages
the Claude and Codex native plugins and links skills into the Codex and Gemini
user skill roots.

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

The plugin ships five **Claude-native** tool-scoped agents in
`plugins/protocols/agents/`. Dispatch them via the Task tool with
an explicit supported `subagent_type`. Their tool restriction is enforced by
agent frontmatter, while Ward keeps each Task actor's protocol phase and mutable
guard state independent from the main manager and sibling workers.

| Agent | `subagent_type` | Tools | Role |
|-------|-----------------|-------|------|
| **scout** | `protocols:scout` | Read, Glob, Grep, Bash, Write (no Edit) | Survey the codebase, cite `file:line`, do not implement |
| **coder** | `protocols:coder` | Read, Glob, Grep, Bash, Edit, Write | Implement the plan with full TDD; commit own work |
| **analyst** | `protocols:analyst` | Read, Glob, Grep, Bash, Write (no Edit) | Find problems — edge cases, security, races; do not fix |
| **verifier** | `protocols:verifier` | Read, Glob, Grep, Bash, Write (no Edit) | Gate the merge; default NO-MERGE |
| **experiment worker** | `protocols:experiment-worker` | Read, Glob, Grep, Bash, Edit, Write | Run one isolated experiment; never promote itself |

These agents are Claude-only. Codex and Gemini do not load Claude plugin agents — they
consume the equivalent doctrine from the `gauntlet` and `subagent` skills' prose.

The script-based installer (`scripts/install_skills.py`) installs the native
Claude and Codex plugins as well as platform skill links. Claude agents load
through Claude's native plugin system: the `agents/` directory is
auto-discovered when the plugin is installed via `claude plugin install`, so no
manifest declaration is required.

## Ward Integration

Protocols that restrict tools use [ward](https://github.com/ctoth/ward) for mechanical enforcement:

1. Ward's lifecycle hooks create/delete actor records and session families.
2. This plugin's **SessionStart** hook validates and installs the bundled
   `protocols-gates` profile; failure is surfaced instead of silently disabling
   enforcement.
3. The main manager alone runs `ward set foreman` (`ward.exe set foreman` from
   Windows-hosted Git Bash), which changes actor `main`.
4. This plugin's **SubagentStart** hook maps supported Claude `agent_type`
   values to actor-local protocol phases. It also maps native Codex
   collaboration's exact, unselectable `default` sentinel, or an omitted type
   accompanied by Codex's required non-empty `turn_id` extension, to the
   distinct `codex-scout` discovery phase. Missing types without that Codex
   discriminator and all unknown/generic types remain `uninitialized`, where
   Bash/Edit/Write fail closed while native Read remains available for diagnosis.
5. Ward gate rules evaluate each actor's independent phase, history, signals,
   and path ownership on every tool call.

Claude exposes plugin agent types with a `protocols:` prefix. The exact logical
Task mapping is `protocols:scout -> scout`, `protocols:coder -> coder`,
`protocols:analyst -> analyst`, `protocols:verifier -> verifier`,
`protocols:researcher -> researcher`, `protocols:adversary -> adversary`, and
`protocols:experiment-worker -> experiment-worker`. Bare values are accepted
only for hosts that emit them without plugin qualification. A physical prompt
and its Task launch parameter must both name the same supported type. Task
workers never run a session-global transition.

Native Codex collaboration workers are not direct CLI workers: the host gives
them a stable `agent_id` and may send `agent_type=default` or omit the type.
Codex's required non-empty `turn_id` lifecycle extension distinguishes the
omitted-type native case from Claude Task. Ward does not infer a protocol role
from prompt text, actor ID, or missing type alone. The hook assigns only the
distinct `codex-scout` phase, which denies Edit and Write and limits Bash to
parsed `rg` commands and the approved read-only Git queries (`status`, `diff`,
`log`, `show`, and `rev-parse`), without redirection or command substitution.
Missing types without `turn_id` and explicit unknown types do not receive this
phase.

Direct Codex/Gemini CLI workers are separate again: launch each with a unique
`WARD_SESSION` and `WARD_ACTOR_ID`, then have that CLI worker run `ward set
<phase>` to select an explicit protocol phase. Hosts that cannot provide either
a real collaboration `agent_id` or an explicit `WARD_ACTOR_ID` cannot safely
run concurrent mechanically enforced roles.

### Gate Rules

| Rule | Phase | Denies |
|------|-------|--------|
| `foreman-gate.yaml` | `foreman` | Bash, Edit, Write (except prompts/ and notes-*) |
| `adversary-gate.yaml` | `adversary` | Edit, Write, Bash |
| `researcher-gate.yaml` | `researcher` | Edit (Write allowed for reports) |
| `experiment-gate.yaml` | `experiment-worker` | Integration-branch moves — `git push`, `merge`, `rebase`, `cherry-pick`, `pull`, `switch`/`checkout` (commit, add, branch, tag stay allowed; override: `ward allow experiment-promote`) |
| `codex-scout-gate.yaml` | `codex-scout` | Edit, Write, and Bash outside the finite parsed read-only discovery grammar |
| `uninitialized-worker-gate.yaml` | `uninitialized` | Bash, Edit, Write until a supported Task role is initialized |

## Installation

### Claude plugin install

```bash
claude plugin marketplace add ctoth/protocols-plugin
claude plugin install protocols@protocols-marketplace
```

### Script-based installer for Codex and Gemini

Use the bundled installer to install the native Codex plugin and Codex skill
links, and/or to install Gemini skill links:

```bash
uv run scripts/install_skills.py doctor
uv run scripts/install_skills.py install --platform codex --trust-codex-hooks
uv run scripts/install_skills.py install --platform gemini
```

What the installer does:

- discovers every `plugins/*/skills/*/SKILL.md` directory;
- installs `protocols@protocols-marketplace` through `codex plugin add`;
- refreshes a stale Codex native plugin with an intentional `codex plugin
  remove` followed by `codex plugin add`;
- queries Codex's live `hooks/list` API and, only with the explicit
  `--trust-codex-hooks` flag, authorizes exactly the active protocols
  `SessionStart` and `SubagentStart` hashes through `config/batchWrite`;
- installs Codex skills into both `~/.agents/skills` and
  `~/.codex/skills/protocols-plugin`;
- installs Gemini skills into `~/.gemini/skills`;
- uses symlinks when possible and managed copies when symlinks are unavailable;
- refuses to overwrite unmanaged destinations unless `--force` is supplied.

Common commands:

```bash
uv run scripts/install_skills.py install --trust-codex-hooks
uv run scripts/install_skills.py install --platform codex --trust-codex-hooks
uv run scripts/install_skills.py install --platform gemini
uv run scripts/install_skills.py install --platform claude
uv run scripts/install_skills.py uninstall
```

`install --platform claude` uses Claude's native `claude plugin
marketplace add/install` flow under the hood. `install --platform codex` keeps
the existing skill-link behavior and also installs or refreshes the native
Codex plugin. Hook authorization is never implicit: when either protocols hook
is new or modified, Codex installation fails with the exact remediation until
`--trust-codex-hooks` is supplied. Omitting `--platform` installs all supported
targets. Restart Codex after any native plugin install, refresh, or trust write
so the new lifecycle hook chain is loaded.

## Required compatibility set

- Protocols Claude and Codex native plugins `0.3.3`
- `protocols-gates` Ward profile `0.3.3`
- Ward revision `cea6f35bdc4dea1180f2bb879dcb3a66f430795d`, built from a clean committed tree
- Ward lifecycle hooks: `PreToolUse eval`, `SubagentStart start-actor`,
  `SubagentStop end-actor`, and `SessionEnd end-session`, each installed by
  `ward install`
- `jq` for safe SubagentStart role parsing
- On Windows, `sh.exe` with `cygpath` from the same POSIX shell distribution
  for native Codex plugin hook execution
- `uv` is required for the script-based installer

`uv run scripts/install_skills.py doctor` checks Claude and Codex independently.
It fails if any Ward capability, revision, Claude lifecycle hook, Codex
lifecycle hook, profile version, installed plugin version, Windows shell
prerequisite, source/cache integrity check, or exact live Codex
`SubagentStart` handler is missing, stale, disabled, untrusted, modified, or
loaded with warnings/errors. Live effective state and source/cache integrity are
reported as separate evidence. A coherent install is proved with:

```bash
ward validate-profile ./plugins/protocols/ward-profile
ward install-profile ./plugins/protocols/ward-profile
ward list-profiles
ward validate
claude plugin update protocols@protocols-marketplace
claude plugin list
uv run scripts/install_skills.py install --platform codex --trust-codex-hooks
codex plugin list --json
uv run scripts/install_skills.py doctor
```

After a Codex refresh, restart Codex before running the separate live native
spawn acceptance. An already-running process retains its previous hook chain.
The separate paid live gate is
`bash scripts/codex_native_worker_acceptance.sh`; deterministic verification
only proves that this harness and its required invariants are present.

## Verification

The deterministic full repository gate is:

```bash
bash scripts/verify.sh
```

The release acceptance gate is deliberately separate because it launches paid
real Claude agents. It creates a disposable Git fixture, runs a real foreman
parent with parallel `scout` and `experiment-worker` Task actors, captures hook
events, checks distinct actor IDs and overlap, verifies nonce-bound reports and
the experiment commit/denials, and checks SessionEnd cleanup:

```bash
bash scripts/ward_actor_acceptance.sh
```

Synthetic profile smoke tests are supporting evidence; they do not replace
this real parent/parallel-worker gate.

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
