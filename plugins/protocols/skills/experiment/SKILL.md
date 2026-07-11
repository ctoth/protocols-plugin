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

For a portfolio of competing hypotheses against one goal metric, run the
campaign protocol (`/protocols:campaign`); it dispatches this protocol once per
confirmed candidate.

## Core Rule

An experiment is not implementation. It is a controlled attempt to learn one
operational fact.

Change one variable at a time. Measure against a committed baseline. Promote
only if the metric gate justifies it. Rigor is enforced by the environment and
the record, not by the worker's honesty: an agent optimizing a metric will
find the metric's implementation, and 72% of observed metric exploits in the
wild come with a confident written rationale. The protocol assumes the worker
is sincere and still checks everything.

## Promotion Authority Rule

The agent that changes the experiment branch does **not** decide whether the
change may land on the integration branch.

Experiment workers may:

- implement the single-variable change on the experiment branch;
- run tests, profiles, and metric gates;
- commit the experiment branch work;
- write the experiment record;
- state a recommendation in the record.

Experiment workers must not:

- switch to the integration branch for promotion;
- merge, rebase, cherry-pick, push, or otherwise move the integration branch;
- treat their own metric interpretation as promotion approval;
- run the promotion step, even if the worker believes the gate passed.

Promotion requires a separate actor after the worker is done:

- a verifier, foreman, or parent agent reads the record and raw command output;
- recomputes the gate math independently from the recorded evidence;
- verifies regression checks and branch cleanliness;
- confirms the source delta is exactly the passing experiment delta;
- then performs the integration-branch merge/push if, and only if, the gate is
  proven to pass.

If a subagent prompt asks a coding worker to promote its own experiment result,
the prompt violates this protocol. Rewrite the prompt before dispatch.

## Preregistration Rule

The experiment record is written and committed **before** the source change,
not after the results exist. A record written after the numbers are known is a
press release, not an experiment.

Preregister, in `experiments/YYYY-MM-DD-short-name.md`, on the experiment
branch, as the first commit after branching:

- the directional hypothesis and the single variable;
- ONE primary metric, its exact command, and the harness state it runs against
  (`git rev-parse HEAD:tests/` or equivalent hash of the evaluator paths);
- the minimum meaningful effect — the smallest delta worth promoting, declared
  before any data;
- the seed/instance plan (which seeds, which benchmark rows, how many runs);
- the analysis plan (paired comparison, median vs mean, CI method);
- kill criteria;
- the falsification condition — what result would prove the hypothesis wrong.

Everything else in the record (results, telemetry, failure analysis,
recommendation) is appended later. **The preregistered fields are frozen.**
The promotion verifier diffs the prereg commit against the final record: if a
hypothesis, metric, threshold, seed plan, or kill criterion changed after data
arrived, the experiment is invalid regardless of the numbers. Secondary
metrics noticed along the way are recorded as exploratory, never substituted
for the primary.

## Sealed Evaluator Rule

The thing being optimized must not be able to edit the thing doing the
measuring.

During the experiment, the worker does not modify tests, benchmark harnesses,
evaluator scripts, gold data, or metric computation — the paths whose hash the
prereg pinned. The known exploit taxonomy is exactly this: tampering with eval
code, special-casing visible tests, weakening match criteria, fabricating
intermediate artifacts, and counting a crash as a pass.

- The promotion verifier runs `git diff <prereg-commit> HEAD -- tests/ eval/
  bench/ benchmarks/` (adjusted to the repo's evaluator paths). Non-empty diff
  = automatic no-go, whatever the metric says.
- If the harness itself is wrong or missing instrumentation, that is a
  separate infrastructure task landed and committed **before** preregistration
  — never a mid-experiment edit.
- Scoring is **fail-closed**: a run only counts as PASS when the harness emits
  a parseable result that passes. Exceptions, timeouts, crashes, and missing
  output are FAIL, never "inconclusive, re-run until green".
- When a sealed holdout exists (campaign protocol, or any tuned change), tune
  against the dev slice only; the holdout is run once, at promotion time, by
  the verifier.

## Measurement Rule

A single benchmark run cannot distinguish an improvement from noise, and
wall-clock noise is right-skewed and machine-load dependent.

- Baseline and experiment run the **same seeds and same instances**, compared
  pairwise per instance — never candidate-run-vs-remembered-number.
- Minimum 3 runs per side for a directional signal; 5+ before recommending
  promotion. If the repo's benchmark is too slow for that, say so in the
  record and shrink the benchmark, don't shrink the run count silently.
- Wall-clock metrics report **median** (or trimmed mean) and spread, never
  bare mean.
- A delta is real only when the paired-difference interval excludes zero AND
  clears the preregistered minimum meaningful effect. Point estimates in the
  right order are not evidence.
- Comparing several configs multiplies false positives; if the experiment
  sweeps variants, the record says so and the verifier judges accordingly
  (Holm-style caution — the more comparisons, the bigger the required margin).
- No peeking-and-stopping on a fixed-run plan: either run the preregistered
  plan to completion, or preregister an early-stop rule explicitly. Stopping
  the moment the numbers look good is p-hacking with extra steps.

## Required Shape

Every experiment must have:

- **Hypothesis**: what should improve and why. (preregistered)
- **Single variable**: the exact code/config/route change under test.
  (preregistered)
- **Baseline**: current branch, command, seeds, and per-seed results before
  the change — a committed artifact, not a remembered number.
- **Experiment branch**: isolated from the integration branch.
- **Fast contracts**: tests or telemetry checks that fail before the full
  benchmark if the idea is wrong.
- **Instrumentation contract**: the reusable telemetry/profiler surface used to
  observe the bottleneck class before changing solver behavior.
- **Metric gate**: exact command, timeout, pass/fail threshold, seed plan, and
  artifacts. (preregistered)
- **Failure-analysis gate**: if the metric gate fails or is ambiguous, profiler
  or equivalent operational evidence explaining whether the intended bottleneck
  moved, shrank, or stayed unchanged.
- **Kill criteria**: when to abandon instead of tuning. (preregistered)
- **Provenance**: enough logged detail (commits, harness hash, seeds, env,
  exact commands, raw output paths) that the result could be re-executed, not
  reconstructed from memory. A result that cannot be reproduced from its
  record is discarded.
- **Record file**: repo-local markdown under `experiments/`, committed at
  prereg time and completed at the end.

## Workflow

1. State the literal outcome and active experiment item before each action.
2. Verify current branch and tracked-file cleanliness.
3. Verify the required instrumentation exists for the bottleneck class. If it
   does not, stop: the next task is instrumentation infrastructure, not an
   experiment.
4. Run the baseline: the preplanned seeds/instances, with instrumentation
   enabled, recording per-run results and the spread. This is the noise floor
   every later claim is judged against.
5. Create a dedicated experiment branch.
6. Run `ward set experiment-worker` to activate enforcement for the worker
   session. Do this after the branch exists (branch creation must happen first)
   and before making any changes — it mechanically blocks the worker from
   pushing, merging, rebasing, cherry-picking, or switching the integration
   branch, and from editing evaluator paths, so promotion authority and the
   sealed evaluator stay intact.
7. **Preregister**: write the record file with the frozen fields (hypothesis,
   single variable, primary metric + harness hash, minimum effect, seed plan,
   analysis plan, kill criteria, falsification condition) and commit it.
8. Make the smallest source/config change that tests the hypothesis.
9. Commit the source/config change with explicit paths.
10. Run fast contracts.
11. Run the preregistered metric gate — same seeds, same instrumentation,
    fail-closed scoring.
12. If the metric gate fails or is ambiguous, run failure analysis before
    calling the experiment complete:
    - use the profiler on the real hot execution path;
    - for Python worker/solver paths, use `py-spy` unless the repository names
      a more specific profiler;
    - use domain telemetry that observes the claimed bottleneck, not only wall
      time;
    - compare against the baseline or previous profile;
    - state whether the dominant cost moved, shrank, or stayed unchanged;
    - name the next target from the evidence.
13. Complete the record: append results, telemetry, failure analysis, and the
    recommendation. Do not touch the preregistered fields.
14. Commit the completed record.
15. Worker decision:
    - **recommend promotion** only if the preregistered gate appears to pass
      on the paired numbers, regression checks hold, and the operational
      reason for the improvement is recorded;
    - **recommend abandon** only after the failed metric has a profiler-backed
      or operationally measured explanation;
    - **incomplete: profile required** if the gate failed but the bottleneck is
      still unknown.
16. Stop worker execution after the experiment record is committed. Do not
    switch to the integration branch. Do not merge. Do not push. Report the
    commit hashes and recommendation to the verifier/foreman/parent.
17. Separate promotion gate (verifier/foreman/parent):
    - read the worker's experiment record and raw command output;
    - **prereg integrity**: diff the prereg commit against the final record —
      any change to frozen fields invalidates the experiment;
    - **sealed evaluator**: diff evaluator paths from prereg commit to HEAD —
      any change is an automatic no-go;
    - independently recompute the metric gate from the recorded per-run
      numbers — paired difference, spread, minimum effect;
    - **adversary pass**: before accepting a win, actively try to explain the
      delta away as leakage, a measurement artifact, a broken contract, or a
      special case. A win nobody tried to kill is unverified;
    - verify regression checks and branch cleanliness;
    - verify the source delta is exactly the intended passing experiment;
    - run the sealed holdout now if one exists;
    - only then merge/push to the integration branch.
18. If abandoning, the separate verifier/foreman/parent records the result on
    the integration branch if needed — negative results are committed
    artifacts, not scratch. Do not merge the failed source delta.

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

Sections marked PREREG are committed before the source change and never edited
afterward.

```markdown
# [Experiment Name]

Date: YYYY-MM-DD

Status: measured on experiment branch; source change [recommended for promotion / not promoted].

Experiment branch: `...`

## Preregistration (PREREG — frozen at commit `...`)

Hypothesis: ...

Single variable: ...

Primary metric:
- Command: `...`
- Evaluator paths + hash: `...`
- Pass threshold: ...
- Minimum meaningful effect: ...

Seed/instance plan: [seeds, benchmark rows, runs per side]

Analysis plan: [paired per-instance comparison; median/trimmed mean for
wall-clock; how the interval is computed]

Kill criteria: ...

Falsification condition: ...

## Baseline

- Command: `...`
- Per-run results: ...
- Median and spread: ...
- Telemetry: ...

## Results

Evidence commits:
- `...` preregistration
- `...` source/config delta
- `...` completed record

Experiment result:
- Command: `...`
- Per-run results: ...
- Median and spread: ...
- Paired per-instance deltas: ...
- Telemetry: ...

Exploratory observations (not the primary metric): ...

Failure analysis:
- Profiler or operational command: `...`
- Compared against: `...`
- Dominant cost before: `...`
- Dominant cost after: `...`
- Interpretation: [moved / shrank / unchanged / invalid measurement]
- Next target from evidence: `...`

Fast contracts:
- `...`

Provenance:
- Code commit: `...`  Harness hash: `...`
- Dataset/benchmark version: `...`
- Environment/machine: `...`
- Raw output artifacts: `...`

Outcome: [positive / weakly positive / negative / invalid]

Worker recommendation: [recommend promotion / recommend abandon / incomplete: profile required]

## Promotion verification

- Verifier/foreman/parent: `...`
- Prereg integrity (frozen fields unchanged): [pass / FAIL]
- Sealed evaluator (evaluator-path diff empty): [pass / FAIL]
- Independent gate calculation: `...`
- Adversary pass (attempted alternative explanations): `...`
- Regression checks: `...`
- Holdout result (if any): `...`
- Integration decision: [promoted / not promoted]

Generated diagnostics:
- `...`

These generated diagnostics were [committed/not committed].
```

## Anti-patterns

- Changing multiple solver routes and then calling the result an experiment.
- Writing the record after the results are known and calling it a hypothesis.
- Moving the threshold, swapping the metric, or rewriting kill criteria once
  data has arrived.
- Editing tests, harness, gold data, or metric code mid-experiment — including
  "fixing" a flaky check the candidate happens to trip.
- Treating a crash, timeout, or unparseable output as anything but FAIL.
- Comparing one lucky run against a remembered baseline number, or unpaired
  runs against each other.
- Declaring victory on a delta smaller than the baseline's own spread.
- Stopping the run early because the numbers currently look good.
- Comparing against stale notes instead of a current committed baseline.
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
- Letting the same coding worker implement the experiment, interpret the metric
  gate, and merge or push the integration branch.
- Accepting a win that no separate actor tried to explain away.
