---
name: iterations
description: Tracked iteration cycles for reducing failures. Number iterations sequentially, record state before/after, commit atomically per fix. Use when iteratively reducing test failures, fixing bugs in cycles, or any work requiring tracked progress across multiple attempts.
disable-model-invocation: false
---

# Iteration Protocol

Use when: iteratively reducing failures, fixing bugs in cycles, any work requiring tracked progress across multiple attempts.

## Structure

```
reports/
  iteration-log.md          # Running summary
  iterations/
    001/
      start.json            # State at iteration start
      end.json              # State at iteration end
      analysis.md           # What was attempted
      clusters/             # If working on multiple fixes
        cluster-a/
          fix.md
          verification.json
```

## Iteration Tracking

Number iterations sequentially: 001, 002, etc.

**Critical rule:** If failures increase from previous iteration, STOP and diagnose before proceeding.

## Per-Iteration Workflow

1. Record starting state -> `start.json`
2. Analyze failures -> `analysis.md`
3. Select targets (2-3 unrelated issues max)
4. For each target:
   - Attempt fix
   - Verify (test must pass)
   - If regression -> revert, document, move on
   - If success -> commit immediately
5. Record ending state -> `end.json`
6. Update `iteration-log.md`
7. Repeat

## State JSON Format

```json
{
  "timestamp": "ISO8601",
  "total": 100,
  "pass": 85,
  "fail": 15,
  "skip": 0
}
```

## iteration-log.md Format

```markdown
# Iteration Log

## 001 - [date]
- Start: 15 failures
- Targets: [list]
- Result: 12 failures (-3)
- Commits: [hashes]

## 002 - [date]
- Start: 12 failures
- Targets: [list]
- Result: 14 failures (+2) WARNING REGRESSION
- Action: Reverted, investigating...
```

## Commit Protocol

One atomic commit per fix, immediately after verification passes.

```
fix(<component>): iteration {N} - <brief description>

Fixes: <what was wrong>
Tests: <what now passes>
```

## Rules

- Never batch multiple fixes into one commit
- Never proceed if failure count increased
- Always verify before committing
- Always record state before and after
- Keep iteration-log.md updated as you go
