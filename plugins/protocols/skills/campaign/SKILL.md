---
name: campaign
description: Multi-hypothesis research campaign protocol for open-ended optimization goals ("make X faster", "improve the metric") where agent-generated or user-supplied ideas compete for a limited budget. Searches prior work, triages ideas cheaply, confirms survivors with preregistered experiments, and keeps dead ideas dead.
disable-model-invocation: false
---

# Campaign Protocol

Use when: an open-ended goal against one metric with more candidate ideas than
budget — "make the solver faster", "cut benchmark regressions", "improve
routing quality". One idea, one change, one measurement is just the experiment
protocol (`/protocols:experiment`); a campaign is a portfolio of them.

## Core Rule

A campaign is a search over hypotheses, not a queue of them. Budget flows
toward evidence: many ideas get a cheap look, few get a full experiment, and
every death is recorded with its reason so the search never revisits it.

## Prior-Art Gate

Before candidate ranking, search the repository's experiment results, failure
records, profiles, notes, history, and relevant literature locations. If no
relevant prior work exists, do not invent a literature dependency or block
indefinitely because a repository has no papers.

An idea recorded as dead is ineligible unless the campaign states what changed
about its cause of death. Memory or chat summaries do not replace the current
repo-local search.

## Roles

- **Manager** (you): frames the goal, prioritizes, dispatches workers, prunes.
- **Experiment workers**: one hypothesis each, dispatched into a dedicated
  branch/worktree prepared before launch.
- **Verifier**: independent promotion gate per the experiment protocol,
  including the adversary pass.

## Phases

### 1. Frame

- Goal metric: exact command, current baseline
  (per-seed numbers, median, spread — the noise floor);
- Campaign budget: how many triage probes and full experiments the goal is
  worth before stopping;
- Holdout: a slice of the benchmark set aside now, excluded from all
  triage and tuning, run only by the verifier at promotion time;
- Kill criteria: e.g. two consecutive rounds with no survivor, or
  budget exhausted.

### 2. Ideate

List candidate hypotheses — from profiles, from failure analyses of past
experiments, from literature. An idea recorded as dead is not retried unless
its cause of death no longer holds. Rank what remains by expected effect and
cost to test; when objectives compete (speed vs correctness vs memory), keep
the non-dominated set rather than forcing a single ranking.

Hypotheses may be agent-generated. Do not ask the user to choose among ordinary
reversible candidates unless the user's domain judgment is itself required
evidence or the choice changes the campaign's approved scope.

### 3. Triage wide

Give each ranked candidate the smallest probe that could kill it: a focused
fixture, a single benchmark row, a profile, 1–2 seeds. Then halve: drop the
worst half, give survivors a bigger slice, repeat while the budget allows.

- Triage results are directional only. **A triage pass is never promotion
  evidence** — it exists to kill ideas cheaply, not to confirm them.
- Every pruned candidate needs an exact cause of death: the number, the
  profile, the contradicting contract. "Didn't look promising" is not a cause
  of death.
- Probes must not touch the holdout.

### 4. Confirm deep

Each surviving candidate becomes one full experiment-protocol run: own branch,
own worker, preregistration before the delta, sealed evaluator, paired seeds,
the works. One hypothesis per worker per branch — a worker that "also tried
something else while in there" has left both protocols.

### 5. Promote

Per the experiment protocol's promotion gate, one experiment at a time, by the
verifier — including the holdout run and the adversary pass. Two survivors
that both pass are still promoted separately; if they interact, the second is
re-measured on top of the first before promotion.

### 6. Synthesize

After each round, decide from evidence: another round, a pivot to
instrumentation, or campaign end. When kill criteria fire, stop instead of
finding one more idea.

## Anti-patterns

- Retrying a killed idea without stating what changed.
- Spending the whole budget confirming the first idea instead of triaging the
  field.
- Treating a triage number as a promotion result.
- Letting one worker carry several hypotheses in one branch.
- Touching the holdout during triage or tuning.
- Pruning without recording the cause of death.
- Adding one more round after campaign kill criteria have fired.
- Ranking candidates before the prior-art search.
- Asking the user to perform routine hypothesis generation that the campaign
  manager exists to automate.
