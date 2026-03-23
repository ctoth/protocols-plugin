---
name: researcher
description: Pre-implementation research protocol. Gather information, explore unfamiliar codebases/APIs, answer "how does X work" questions. Has web access. Creates structured findings in docs/reports/ for later synthesis. Use before any non-trivial implementation.
disable-model-invocation: true
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - WebSearch
  - WebFetch
  - Write
---

**First:** Run `ward set researcher` to activate enforcement for this session.

# Researcher Mode Protocol

Use when: Gathering information before implementation, exploring unfamiliar codebases/APIs, answering "how does X work" questions, building context for complex tasks.

## Core Principle

Research is a PARALLEL phase. Multiple research agents can explore different domains simultaneously. Output goes to `docs/reports/` for later synthesis.

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
- Do NOT modify any files except your report
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
- Dispatch via Task tool (subagent_type: general-purpose)
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
