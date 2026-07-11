---
name: campaign
description: Multi-hypothesis research campaign protocol. Use for open-ended optimization goals ("make X faster", "improve the metric") where several candidate ideas compete for a limited budget. Triages ideas cheaply, confirms survivors with full preregistered experiments, and keeps a committed ledger so dead ideas stay dead.
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

The campaign manager coordinates and never implements — run `ward set foreman`
and follow the foreman protocol for all dispatch. Workers run the experiment
protocol; the manager runs the portfolio.

## Roles

- **Manager** (you): frames the goal, maintains the ledger, prioritizes,
  dispatches workers, prunes. Never edits source, never runs benchmarks.
- **Experiment workers**: one hypothesis each, on the experiment protocol,
  under `ward set experiment-worker`. Never promote themselves.
- **Verifier**: independent promotion gate per the experiment protocol,
  including the adversary pass.

## Phases

### 1. Frame

Commit `experiments/INDEX.md` (the ledger) with:

- the goal metric: exact command, current baseline as a committed artifact
  (per-seed numbers, median, spread — the noise floor);
- the campaign budget: how many triage probes and full experiments the goal is
  worth before stopping;
- the holdout: a slice of the benchmark set aside now, excluded from all
  triage and tuning, run only by the verifier at promotion time;
- campaign kill criteria: e.g. two consecutive rounds with no survivor, or
  budget exhausted.

No candidate work starts before the ledger commit exists.

### 2. Ideate

List candidate hypotheses — from profiles, from failure analyses of past
experiments, from literature. For each candidate check the ledger first: an
idea recorded as dead is not retried unless the entry's "why it died" no
longer holds (and the new entry must say what changed). Rank what remains by
expected effect and cost to test; when objectives compete (speed vs
correctness vs memory), keep the non-dominated set rather than forcing a
single ranking.

### 3. Triage wide

Give each ranked candidate the smallest probe that could kill it: a focused
fixture, a single benchmark row, a profile, 1–2 seeds. Then halve: drop the
worst half, give survivors a bigger slice, repeat while the budget allows.

- Triage results are directional only. **A triage pass is never promotion
  evidence** — it exists to kill ideas cheaply, not to confirm them.
- Every pruned branch gets a ledger line stating what killed it: the number,
  the profile, the contradicting contract. "Didn't look promising" is not a
  cause of death.
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

After each round, update the ledger: statuses, causes of death, what the
profiles now say the dominant cost is, and the honest yield (candidates tried
vs promoted — expect most to die; a round where everything "worked" is a
measurement problem, not a triumph). Decide from evidence: another round, a
pivot to instrumentation, or campaign end. When kill criteria fire, stop —
write the final synthesis instead of finding one more idea.

## Ledger Template

`experiments/INDEX.md`:

```markdown
# Campaign: [goal]

Goal metric: `command` — baseline [median ± spread] at commit `...`
Holdout: [slice definition] — untouched until promotion
Budget: [N triage probes / M full experiments]; kill: [criteria]

| ID | Hypothesis | Status | Evidence | Cause of death / result |
|----|------------|--------|----------|-------------------------|
| 01 | ...        | triaged-out | [probe cmd + number] | slower on focused row (+8% median) |
| 02 | ...        | promoted    | experiments/2026-...md | +14% median, holdout confirmed |
| 03 | ...        | no-go; diagnosis incomplete | experiments/2026-...md | gate missed; profile pending |

## Round log

### Round 1 — [date]
Candidates: ... Probes: ... Survivors: ... Yield: 1/6.
Dominant cost after round: [from profile evidence]
```

## Anti-patterns

- Retrying an idea the ledger already killed, without stating what changed.
- Spending the whole budget confirming the first idea instead of triaging the
  field.
- Treating a triage number as a promotion result.
- Letting one worker carry several hypotheses in one branch.
- Touching the holdout during triage or tuning.
- Pruning without recording the cause of death.
- The manager "quickly checking" a number itself instead of dispatching.
- Ending a round with no ledger update.
- Adding one more round after campaign kill criteria have fired.
