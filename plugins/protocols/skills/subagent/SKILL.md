---
name: subagent
description: Background knowledge for writing and launching subagent prompts. Covers prompt file conventions, worker identity declarations, batch dispatch patterns, and parallel swarm safety. Auto-invocable when dispatching agents.
disable-model-invocation: false
---

# Subagent Protocol

Use when: launching delegated work — claude agents via the Task tool, or CLI agents (Codex/Gemini) directly.

## Subagents come in two kinds

- **Claude agents** — dispatched via the `Task` tool. Most of this skill is
  about these.
- **CLI agents** — Codex, Gemini, and other external reviewer/agent CLIs.
  Dispatched by running their CLI directly (e.g.
  `codex exec --dangerously-bypass-approvals-and-sandbox "..."`), NOT via the
  Task tool. See the `external-agents` skill for invocation details.

A CLI agent IS a subagent. Running its CLI is the dispatch act — the shell
equivalent of the Task tool. **NEVER wrap a CLI agent inside a Task subagent**
(spawning a claude agent just to type the CLI command). That is
double-dispatch: wasted wall-clock and tokens, and it buries the external
agent's independent judgement behind a claude proxy. Run the CLI directly.

The prompt-file conventions in this skill (physical prompt file, single
deliverable, exact paths, report location) apply to BOTH kinds — a CLI agent
reads the same kind of prompt file. The worker-identity declaration and the
agent-type rule (see "CRITICAL: Agent Type") apply ONLY to claude Task agents.

## CRITICAL: Agent Type

Dispatch an explicit plugin role: `subagent_type: protocols:scout`,
`protocols:coder`, `protocols:analyst`, `protocols:verifier`, or
`protocols:experiment-worker`. Claude qualifies plugin agent types with the
`protocols:` namespace. The SubagentStart hook maps those exact host values
to the unprefixed Ward phases `scout`, `coder`, `analyst`, `verifier`,
`researcher`, `adversary`, and `experiment-worker`. Unknown and
generic types remain `uninitialized`; Ward allows native Read for diagnosis but
denies Bash/Edit/Write. Never use `general-purpose` as a fallback.

Native Codex collaboration is a separate host surface from Claude Task. It
provides a stable actor ID but only the exact, unselectable `agent_type` value
`default`. The SubagentStart hook maps that sentinel to the distinct
`codex-scout` phase: native Read remains available, Edit and Write are denied,
and Bash is limited to the profile's finite parsed read-only discovery grammar.
This is not protocol-role inference; missing and every other unknown type stay
`uninitialized` and fail closed.

Direct Codex/Gemini CLI workers are separate from both Claude Task and native
Codex collaboration. Launch each with unique `WARD_SESSION` and
`WARD_ACTOR_ID` values, then let that worker select its explicit phase with
`ward set <phase>` (`ward.exe` from Windows-hosted Git Bash). The `default` to
`codex-scout` mapping does not apply to direct CLI workers.

NEVER use READ-ONLY agent types (Explore, Plan, or similar) as workers, even in planning mode — they cannot write report files to `./reports/` and will fail. Since subagents must write reports, the type you pick MUST be write-capable.

## The Problem

Subagents start fresh. They don't know directory structure, file paths, common workarounds, or project conventions. Inline prompts get long, lose context, and you forget critical info.

## Solution: Physical Prompt Files

Always write prompts to files. This provides:
- Context preservation (subagent gets full instructions)
- Audit trail (prompts/ shows what was dispatched)
- Reusability (patterns become templates)

## Directory Convention

```
project/
├── prompts/     # Subagent task prompts (input)
└── reports/     # Subagent deliverables (output)
```

Before launching any subagent, ensure both directories exist.

## CRITICAL: Worker Identity Declaration

Every subagent prompt MUST start with this line before anything else:

> **You are a WORKER agent launched via the Task tool. Execute this task directly. Do NOT read foreman.md. Do NOT coordinate — DO the work yourself.**

Immediately after that line, name the exact Task type and actor phase:

> **Ward role: launch with `subagent_type: protocols:coder`. The SubagentStart hook initializes only this Task actor to phase `coder`; do not run `ward set`.**

Both lines go at the very top of every physical prompt AND in the Task tool's
prompt parameter. Replace `protocols:coder` and phase `coder` with the selected
supported host type and mapped phase. This duplication is non-negotiable.

## Prompt File Template

Write to `./prompts/{task-name}.md`:

```markdown
**You are a WORKER agent launched via the Task tool. Execute this task directly. Do NOT read foreman.md. Do NOT coordinate — DO the work yourself.**
**Ward role: launch with `subagent_type: protocols:coder`. The SubagentStart hook initializes only this Task actor to phase `coder`; do not run `ward set`.**

# Task: [Clear Title]

## Context
[What the subagent needs to know about the project state]

## Objective
[Single, specific deliverable]

## Files to Read
- `exact/path/to/file.py` - why relevant

## Files to Modify
- `exact/path/to/file.py` - what to change

## Test Command
` ``bash
[exact command to verify success]
` ``

## Output
Write findings/status to `./reports/{task-name}-report.md`

## CRITICAL: File Modified Error Workaround

If Edit/Write fails with "file unexpectedly modified":
1. Read the file again with Read tool
2. Retry the Edit
3. Try path formats: `./relative`, `C:/forward/slashes`, `C:\back\slashes`
4. NEVER use cat, sed, echo - always Read/Edit/Write
5. If all formats fail, STOP and report - do not use bash workarounds
```

## Launching

In Task tool message:
```
**Ward role: launch with `subagent_type: protocols:coder`. The SubagentStart hook initializes only this Task actor to phase `coder`; do not run `ward set`.**
@prompts/{task-name}.md

Execute this task. Write your report to ./reports/{task-name}-report.md when done.
```

## Scoping Rule

ONE task, ONE deliverable.

Bad: "Run tests, find failures, analyze causes, fix them, document findings"
Good: "Run tests, capture output to report file"

If prompt has multiple verbs (run, compare, analyze, fix, document), you're asking too much.

## Prompt Length Matches Task Size

One-sentence task = one-sentence prompt. State the goal, not the process. Agents are competent — don't hand-hold. A 50-line prompt for "download a screenshot" is you wasting everyone's time. If you can say it in one sentence, the prompt IS one sentence.

## Batch Dispatch — One Template, Many Agents

When dispatching N subagents doing the same task on different inputs (e.g., processing 7 papers, fixing 5 files), write **ONE** template prompt file. Each agent references the same `@prompts/batch-taskname.md` with only the varying parameter (URL, path, title) in the Task tool's prompt field. Do NOT write N near-identical prompt files.

## CRITICAL: Scout Prompts — Verify, Don't Speculate

Every scout prompt MUST include this constraint:

> **Do not speculate. Every claim in your report must be verified by reading source code or observing test output. If you cannot verify something, say "I did not verify this" — do not use words like "may", "possibly", "might", "could be", or "likely". If you don't know, say you don't know. Trace the actual code path. Read the actual source. An unverified theory presented as a finding is worse than no finding at all.**

This is not optional. This goes in every scout prompt. Every single one.

## Checklist Before Dispatch

- [ ] Worker identity declaration at top of prompt (both file AND Task tool prompt param)
- [ ] Exact supported `subagent_type` and matching actor phase stated in both places
- [ ] Prompt written to physical file
- [ ] Single clear deliverable
- [ ] Exact file paths included
- [ ] Test/verification command included
- [ ] File-modified workaround included
- [ ] Output location specified
- [ ] NO-ONELINERS rule restated verbatim and prominently in the prompt — workers do NOT auto-load this skill, so the dispatcher must copy it into every coder/worker prompt
- [ ] "No skipped tests" stated explicitly (if testing)
- [ ] If scout: "verify, don't speculate" constraint included (see above)
- [ ] Every factual claim about code cites a source (scout report file:line, or code you read yourself)
- [ ] If foreman mode: prompt contains NO implementation details — only objective, file, constraints, and a reference to the scout report
- [ ] No "Root Cause", "Fix Required", "Key Insight", or "Context" sections that describe code behavior without a citation
- [ ] If the task is an experiment, benchmark, performance optimization,
      solver comparison, or routing trial: the worker prompt explicitly forbids
      switching to, merging into, rebasing, cherry-picking onto, pushing, or
      otherwise moving the integration branch. Worker may recommend promotion
      only; a separate verifier/foreman/parent must independently verify and
      promote. A Claude Task experiment must use
      `subagent_type: protocols:experiment-worker`; its dedicated
      branch/worktree exists before dispatch and SubagentStart initializes only
      that Task actor. It
      must not run `ward set`. A direct Codex/Gemini worker instead launches
      with unique `WARD_SESSION` and `WARD_ACTOR_ID` values and runs
      `ward set experiment-worker` after entering its already-created branch
      (`ward.exe set experiment-worker` from Windows-hosted Git Bash).

## CRITICAL: Parallel Swarm Awareness

You may be running alongside other agents in parallel.

**FORBIDDEN GIT COMMANDS - NEVER USE THESE:**
- `git stash` - DESTROYS uncommitted work across the entire repo
- `git restore` - overwrites files
- `git checkout` - overwrites files
- `git reset` - destroys commits/changes
- `git clean` - deletes untracked files

If you mess up a file beyond repair: STOP, write what happened to your report, exit.
Foreman will decide what to do.
Do NOT try to "fix" or "clean up" - you'll destroy other agents' work.

## CRITICAL: Never Overwrite Existing Prompts

Prompt files are an audit trail. If `prompts/scout-foo.md` already exists from a previous session, do NOT overwrite it. Pick a new name: `prompts/scout-foo-v2.md`, `prompts/scout-foo-format.md`, or any descriptive variant. Filenames are not a scarce resource. Overwriting destroys the record of what was dispatched before.

## CRITICAL: No Oneliners

**Never write `python -c "..."` or `uv run python -c "..."`.** Not even for "quick" checks. Write a `.py` file, then run it.

**Why:** A `python -c` oneliner evaporates after one use. The next agent that needs the same data must regenerate the entire thing from scratch. A script file is a reusable artifact: write once, run forever, zero marginal token cost.

Write to `scripts/something.py` first, then `uv run python scripts/something.py`. No exceptions.

**Workers do not auto-load this skill.** The dispatcher MUST restate this rule, in full and prominently, in every coder/worker prompt file — otherwise the worker has no source for it and will reach for oneliners. See the dispatch checklist.

## Rules

1. ALWAYS write prompt to physical file first
2. ALWAYS reference with @prompts/filename.md
3. ALWAYS specify output location in ./reports/
4. NEVER write multi-paragraph inline prompts
5. NEVER let subagent ask questions - give everything upfront
6. ALWAYS include parallel swarm warning in prompts
7. NEVER overwrite an existing prompt file - use a new name instead
8. NEVER write python -c oneliners - always write to a .py file first
