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
- **Instrumentation contract**: the reusable telemetry/profiler surface used to
  observe the bottleneck class before changing solver behavior.
- **Metric gate**: exact command, timeout, pass/fail threshold, and artifacts.
- **Failure-analysis gate**: if the metric gate fails or is ambiguous, profiler
  or equivalent operational evidence explaining whether the intended bottleneck
  moved, shrank, or stayed unchanged.
- **Kill criteria**: when to abandon instead of tuning.
- **Record file**: repo-local markdown under `experiments/`.

## Workflow

1. State the literal outcome and active experiment item before each action.
2. Verify current branch and tracked-file cleanliness.
3. Verify the required instrumentation exists for the bottleneck class. If it
   does not, stop: the next task is instrumentation infrastructure, not an
   experiment.
4. Run or locate the baseline metric and baseline telemetry before editing
   production code.
5. Create a dedicated experiment branch.
6. Make the smallest source/config change that tests the hypothesis.
7. Commit the source/config change with explicit paths.
8. Run fast contracts.
9. Run the smallest meaningful metric gate with the same instrumentation
   enabled.
10. If the metric gate fails or is ambiguous, run failure analysis before
   calling the experiment complete:
   - use the profiler on the real hot execution path;
   - for Python worker/solver paths, use `py-spy` unless the repository names a
     more specific profiler;
   - use domain telemetry that observes the claimed bottleneck, not only wall
     time;
   - compare against the baseline or previous profile;
   - state whether the dominant cost moved, shrank, or stayed unchanged;
   - name the next target from the evidence.
11. Write `experiments/YYYY-MM-DD-short-name.md`.
12. Commit the experiment record.
13. Decide:
    - **promote** only if the metric gate passes, regression checks hold, and
      the operational reason for the improvement is recorded;
    - **abandon** only after the failed metric has a profiler-backed or
      operationally measured explanation;
    - **incomplete: profile required** if the gate failed but the bottleneck is
      still unknown.
14. If abandoning, switch back to the integration branch and record the result
    there. Do not merge the failed source delta.

## Instrumentation Rule

Do not start or continue optimization experiments against an opaque bottleneck.

If the available tooling cannot distinguish where the bottleneck lives, first
build or enable reusable instrumentation for that bottleneck class. The
instrumentation is infrastructure, not the experiment. Only after it exists can
an experiment test a single solver/config/encoding hypothesis.

For solver experiments, the instrumentation must be able to separate the
relevant layers for the domain. Examples:

- routing decision vs backend execution;
- preprocessing/residual shape vs core solve;
- grounding size vs solving search;
- rule-family or predicate-family growth in generated encodings;
- assignment/propagation churn for watched domain literals;
- worker/wrapper overhead vs real child-process work.

If the experiment uses a solver with public observer/statistics/propagator APIs,
read and cite those APIs before declaring the solver opaque or selecting a
proxy measurement. If the APIs are insufficient, record that verified limit and
name the external telemetry used instead.

## Profiling Rule

For performance work, profiling is not optional once simple timing stops being
decisive.

Use the profiler on the real execution path. Do not profile a wrapper when the
hot work happens in a worker. Do not stop a configured long profile merely
because it is quiet.

Profile before inventing a second optimization after the first miss. If the
metric is still far from the gate, the next experiment should be selected from
profile evidence, not from intuition.

## Failure Semantics

A promotion gate and an experiment result are different things.

- **Promotion no-go** means the code/config change did not earn its way onto
  the integration branch.
- **True experiment failure** means the no-go has been diagnosed: the record
  names the remaining bottleneck, the measurement that proves it, and the next
  target or why no target exists.

Do not write "failed", "complete", or "abandon" as the final experiment outcome
for performance work when the only evidence is that the benchmark timed out or
missed the threshold. In that state the correct status is:
`promotion no-go; diagnosis incomplete`.

An experiment record for a failed performance gate must answer:

- What instrumentation was available before the source/config change?
- What baseline telemetry did it produce?
- Did the intended operational invariant change?
- Did the hot path move, shrink, or stay the same?
- Was the profiler attached to the real worker/solver process?
- What exact next target follows from the profile?

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
- Telemetry: ...

Experiment result:
- Command: `...`
- Result: ...
- Telemetry: ...

Failure analysis:
- Profiler or operational command: `...`
- Compared against: `...`
- Dominant cost before: `...`
- Dominant cost after: `...`
- Interpretation: [moved / shrank / unchanged / invalid measurement]
- Next target from evidence: `...`

Fast contracts:
- `...`

Metric gate:
- `...`

Outcome: [positive / weakly positive / negative / invalid]

Decision: [promote / abandon / incomplete: profile required]

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
- Treating "0 solved", "timed out", or "no improvement" as a complete
  experiment result without failure analysis.
- Abandoning a performance branch after a metric miss without recording whether
  the bottleneck moved, shrank, or stayed unchanged.
- Merging a branch because it is "somewhat faster" while still missing the
  actual gate.
