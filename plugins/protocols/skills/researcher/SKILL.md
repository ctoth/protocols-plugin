---
name: researcher
description: Pre-implementation research protocol. Gather information, explore unfamiliar codebases/APIs, answer "how does X work" questions. Has web access. Creates structured findings in docs/reports/ for later synthesis. Use before any non-trivial implementation.
disable-model-invocation: false
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - WebSearch
  - WebFetch
  - Write
---

# Researcher Mode Protocol

## Activate The Role By Host

- **Claude Code Task:** Launch with `subagent_type: protocols:researcher`.
  The SubagentStart hook initializes that Task actor to `researcher`. Do not run
  `ward set`; write the requested report artifact directly.
- **Native Codex collaboration:** Use the internal collaboration harness. The
  `foreman` parent writes the physical prompt, then calls `spawn_agent` with
  `fork_turns: "none"`. The message's first line is exactly
  `WARD-DELEGATE/1 phase=researcher`; the real task follows it. Ward rewrites
  the allowed spawn so the child's exact first action is
  `ward accept-delegation <token>`, then binds `researcher` to the opaque host
  actor ID. The child writes the report under that actor-local phase and never
  runs `ward set`. No parent actor snapshot or binding restore is needed.
  A Codex parent must not self-launch `codex exec` for this role.
- **Main session or external CLI:** A main-session researcher runs `ward set
  researcher`. A concurrent external CLI worker must be launched with its own
  `WARD_SESSION` and `WARD_ACTOR_ID`
  before running that command; never reuse the parent or a sibling identity.

## Core Principle

Research is a PARALLEL phase. Multiple research agents can explore independent
domains simultaneously. Claude researchers, capability-authorized native Codex
researchers, and actor-bound external CLI researchers write to `docs/reports/`.

## When to Use

- Before any non-trivial implementation
- When you don't understand the existing code
- When multiple areas need investigation
- When building context would overflow a single agent

## Structure

```
docs/
├── reports/    # Research output (one per domain/question)
└── notes/      # Working observations, scratch
```

## Research Agent Template

Write to `prompts/research-{topic}.md`:

```markdown
# Research: [Topic]

## Question
[Single, specific question to answer]

## Scope
- Look at: [specific files/areas]
- Ignore: [out of scope areas]

## Output
Write findings to `docs/reports/{topic}.md` with:
- Facts (verified with evidence)
- Patterns observed
- Open questions
- Recommendations for next steps

## Constraints
- Do NOT implement anything
- If you find something surprising, document it - don't fix it
```

## Parallel Research Pattern

When multiple domains need investigation:

```
[Research Phase] - PARALLEL
    ├── Agent A: "How does auth work?" -> docs/reports/auth.md
    ├── Agent B: "What's the data model?" -> docs/reports/data-model.md
    └── Agent C: "How are errors handled?" -> docs/reports/errors.md
              │
              v
[Synthesis] - SEQUENTIAL (you, or single agent)
    └── Read all reports -> unified understanding -> plan
```

## Investigation Escalation

If research hits unexpected behavior:

- **L1**: Note it in report, continue
- **L2**: Create `investigations/{topic}.md`, apply investigation protocol
- **L3**: Dispatch external reviewer (Codex/Gemini) for second opinion

## Foreman Role in Research

As foreman during research:
- Write prompt files to `prompts/research-*.md`
- In Claude Code, dispatch `subagent_type: protocols:researcher`
- In Codex, use the `WARD-DELEGATE/1 phase=researcher` `spawn_agent` request
  above with `fork_turns: "none"`; never use `codex exec` to create the child
- For an external Codex/Gemini CLI researcher, assign unique `WARD_SESSION` and
  `WARD_ACTOR_ID` values and require `ward set researcher`
- Read reports from `docs/reports/`
- Do NOT read source code directly - that's the researcher's job
- Synthesize findings into plan

## Anti-patterns

- Researching and implementing in same agent (context pollution)
- Single agent for multiple unrelated domains (serial bottleneck)
- Skipping research because "it looks simple"
- Not writing findings down (knowledge trapped in context)
- Foreman reading source directly instead of delegating

## Exit Criteria

Research phase complete when:
- All questions have documented answers
- No major unknowns remain
- Enough context exists to write implementation plan
- Reports reference specific files/line numbers (not vague)

## Quick Reference

| Situation | Action |
|-----------|--------|
| "How does X work?" | Research agent |
| Multiple domains | Parallel research agents |
| Unexpected behavior found | Escalate per investigation protocol |
| Need second opinion | External agent (Codex/Gemini) |
| Ready to implement | Exit research, enter planning |
