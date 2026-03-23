---
name: investigation
description: Structured debugging with competing hypotheses and escalation levels. Use when encountering unexpected behavior, multiple possible causes, or after 3+ failed fix attempts. Separates facts from theories and tracks evidence systematically.
disable-model-invocation: true
---

# Investigation Protocol

Use when: unexpected behavior, multiple possible causes, debugging > 3 failed attempts.

## Escalation Levels

- **L1**: Single hypothesis, quick verify/fix. No file needed.
- **L2**: 2-3 competing hypotheses. Create investigation file.
- **L3**: Full Gauntlet + external review (Codex/Gemini).

Start at L1. Escalate when stuck.

## Setup

1. Create `investigations/[topic].md` in project root
2. Commit to understanding before fixing

## Structure

Separate FACTS (verified, have evidence) from THEORIES (plausible, untested).

Maintain several competing hypotheses. Chasing a single theory is confirmation bias with extra steps.

## Process

For each test:
- What: exact action taken
- Why: which theory this tests
- Found: actual result
- Means: what this rules in/out

Before each action: state hypothesis.
After each action: record result.

## Template

```markdown
# Investigation: [topic]

## Facts (verified)
- [thing] - evidence: [how verified]

## Theories (plausible)
1. [theory A] - would explain [X], predicts [Y]
2. [theory B] - would explain [X], predicts [Z]
3. [theory C] - would explain [W], predicts [Y]

## Tests Run

| Test | Hypothesis | Result | Rules Out | Supports |
|------|------------|--------|-----------|----------|
| | | | | |

## Current Best Theory
[Which theory survives the evidence, and why]

## Open Questions
-

## Next Action
[What to try next and what it would tell us]
```

## Exit Criteria

- One theory clearly explains all facts
- Can predict what will happen before testing
- Fix addresses root cause, not just symptom

## Anti-patterns

- "This should work" (your model is wrong, not reality)
- Changing multiple things at once
- Abandoning the investigation file mid-debug
- Fixing without understanding
