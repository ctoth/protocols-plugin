---
name: experiment
description: Controlled benchmark experiment protocol for solver, performance, routing, and optimization work. Use when testing a hypothesis against metrics, comparing implementations, or deciding whether to promote or abandon a benchmark-driven change.
disable-model-invocation: false
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Write
  - Edit
---

# Experiment Protocol

Use when: solver work, performance work, routing changes, benchmark-driven
optimization, or any hypothesis that can pass tests but still fail the metric
that matters.

## Core Rule

An experiment is not implementation. It is a controlled attempt to learn one
operational fact.

Change one variable at a time. Measure against a committed or clearly recorded
baseline. Promote only if the metric gate justifies it.

## Required Shape

Every experiment must have:

- **Hypothesis**: what should improve and why.
- **Single variable**: the exact code/config/route change under test.
- **Baseline**: current branch, command, metric, and result before the change.
- **Experiment branch**: isolated from the integration branch.
- **Fast contracts**: tests or telemetry checks that fail before the full
  benchmark if the idea is wrong.
- **Metric gate**: exact command, timeout, pass/fail threshold, and artifacts.
- **Kill criteria**: when to abandon instead of tuning.
- **Record file**: repo-local markdown under `experiments/`.

## Workflow

1. State the literal outcome and active experiment item before each action.
2. Verify current branch and tracked-file cleanliness.
3. Run or locate the baseline metric before editing production code.
4. Create a dedicated experiment branch.
5. Make the smallest source/config change that tests the hypothesis.
6. Commit the source/config change with explicit paths.
7. Run fast contracts.
8. Run the smallest meaningful metric gate.
9. Write `experiments/YYYY-MM-DD-short-name.md`.
10. Commit the experiment record.
11. Decide:
    - **promote** only if the metric gate passes and regression checks hold;
    - **abandon** if the gate fails, the effect is too small, or the result is
      ambiguous;
    - **profile next** if time moved but the bottleneck is still unknown.
12. If abandoning, switch back to the integration branch and record the result
    there. Do not merge the failed source delta.

## Profiling Rule

For performance work, profiling is not optional once simple timing stops being
decisive.

Use the profiler on the real execution path. Do not profile a wrapper when the
hot work happens in a worker. Do not stop a configured long profile merely
because it is quiet.

Profile before inventing a second optimization after the first miss. If the
metric is still far from the gate, the next experiment should be selected from
profile evidence, not from intuition.

## Record Template

```markdown
# [Experiment Name]

Date: YYYY-MM-DD

Status: measured on experiment branch; source change [promoted/not promoted].

Experiment branch: `...`

Evidence commits:
- `...` source/config delta
- `...` experiment record

Hypothesis: ...

Single variable: ...

Baseline:
- Command: `...`
- Result: ...

Experiment result:
- Command: `...`
- Result: ...

Fast contracts:
- `...`

Metric gate:
- `...`

Outcome: [positive / weakly positive / negative / invalid]

Decision: [promote / abandon / profile next]

Generated diagnostics:
- `...`

These generated diagnostics were [committed/not committed].
```

## Anti-patterns

- Changing multiple solver routes and then calling the result an experiment.
- Comparing against stale notes instead of a current baseline.
- Promoting a benchmark-only win that violates semantic contracts.
- Treating generated logs, CSVs, profiles, or screenshots as source progress.
- Re-running a huge full benchmark before a focused row or fixture can fail.
- Guessing the next optimization when a profiler can answer.
- Merging a branch because it is "somewhat faster" while still missing the
  actual gate.
