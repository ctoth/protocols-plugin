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

Campaign managers may autonomously generate, rank, prune, and test hypotheses
on development data. That is the point of the protocol. A broad user request
to optimize a metric authorizes reversible search within its stated scope and
the recorded campaign budget; it does not authorize changing the goal,
expanding the budget, or consuming an irreversible evaluation surface.

## Prior-Art Gate

Before candidate ranking, dispatch a research worker to search the repository's
experiment ledgers, failure records, profiles, notes, history, and relevant
literature locations. The worker commits a search record that names the
locations and terms searched and summarizes every relevant hit. If no relevant
prior work exists, record `none found`; absence after a documented search is a
valid clean prior. Do not invent a literature dependency or block indefinitely
because a repository has no papers. The foreman/manager reads and uses the
artifact but does not write it.

An idea recorded as dead is ineligible unless the campaign states what changed
about its cause of death. Memory or chat summaries do not replace the current
repo-local search.

## Irreversible-Action Authority

A verifier recommendation does not authorize a real, one-time, costly, or
otherwise irreversible holdout. Before opening one, stop and obtain a new user
message authorizing the exact evaluation identity and candidate commit. A CLI
flag, broad `go`, plan language, or another agent's approval is insufficient.

Reversible development probes within the campaign frame do not require a user
checkpoint. Ask only before an irreversible action, a goal/scope change, or a
budget expansion.

The campaign manager coordinates and never implements — run `ward set foreman`
(`ward.exe set foreman` from Windows-hosted Git Bash) for the main actor and
follow the foreman protocol for all dispatch. Workers run the experiment
protocol; the manager runs the portfolio. The foreman gate blocks the manager
from writing or committing anything outside `prompts/` and `notes-*` — so the
ledger, like all durable artifacts, is written and committed by dispatched
workers, never by the manager's own hands. The manager decides every word of
a ledger update; a worker types it.

## Roles

- **Manager** (you): frames the goal, owns the ledger's content, prioritizes,
  dispatches workers, prunes. Never edits source, never runs benchmarks,
  never writes the ledger directly — every ledger create/update is included
  in a dispatched worker's prompt (the worker appends its line and commits).
- **Experiment workers**: one hypothesis each, dispatched into a dedicated
  branch/worktree prepared before launch. Claude uses
  `subagent_type: protocols:experiment-worker`; a native Codex Foreman uses
  `spawn_agent` with `fork_turns: "none"` and the exact first message line
  `WARD-DELEGATE/1 phase=experiment-worker`. The child's exact first action is
  the Ward-injected `ward accept-delegation <token>`. The worker never chooses
  its own phase, runs `ward set`, or promotes itself. Direct CLI workers are
  only for explicitly external-agent use, not for a Codex parent to launch a
  Codex child.
- **Verifier**: independent promotion gate per the experiment protocol,
  including the adversary pass.

## Phases

### 1. Frame

Dispatch a worker to create and commit `experiments/INDEX.md` (the ledger)
with:

- the goal metric: exact command, current baseline as a committed artifact
  (per-seed numbers, median, spread — the noise floor);
- the campaign budget: how many triage probes and full experiments the goal is
  worth before stopping;
- the holdout: a slice of the benchmark set aside now, excluded from all
  triage and tuning, run only by the verifier at promotion time;
- campaign kill criteria: e.g. two consecutive rounds with no survivor, or
  budget exhausted.
- the prior-art search artifact and the exact boundary between autonomous
  development work and user-authorized irreversible actions.

No candidate work starts before the ledger commit exists.

### 2. Ideate

List candidate hypotheses — from profiles, from failure analyses of past
experiments, from literature. For each candidate check the ledger first: an
idea recorded as dead is not retried unless the entry's "why it died" no
longer holds (and the new entry must say what changed). Rank what remains by
expected effect and cost to test; when objectives compete (speed vs
correctness vs memory), keep the non-dominated set rather than forcing a
single ranking.

Hypotheses may be agent-generated. Do not ask the user to choose among ordinary
reversible candidates unless the user's domain judgment is itself required
evidence or the choice changes the campaign's approved scope.

### 3. Triage wide

Give each ranked candidate the smallest probe that could kill it: a focused
fixture, a single benchmark row, a profile, 1–2 seeds. Then halve: drop the
worst half, give survivors a bigger slice, repeat while the budget allows.

- Triage results are directional only. **A triage pass is never promotion
  evidence** — it exists to kill ideas cheaply, not to confirm them.
- Every pruned branch gets a ledger line stating what killed it: the number,
  the profile, the contradicting contract. "Didn't look promising" is not a
  cause of death. Each probe worker's prompt includes the ledger-line duty:
  append the result to `experiments/INDEX.md` and commit it.
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

Keep candidate source on its experiment branch through holdout evaluation.
After explicit user authorization, run the holdout from a clean checkout of
the exact candidate commit. Only a holdout-passing source delta may reach the
integration branch. For a failed candidate, bring back only its ledger update
and evidence; do not merge the source and then create integration reverts.

### 6. Synthesize

After each round, dispatch a ledger update: statuses, causes of death, what
the profiles now say the dominant cost is, and the honest yield (candidates tried
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
- The manager writing or committing the ledger itself — the foreman gate
  blocks it, and durable artifacts are worker deliverables.
- Ending a round with no ledger update.
- Adding one more round after campaign kill criteria have fired.
- Ranking candidates before the prior-art search is committed.
- Asking the user to perform routine hypothesis generation that the campaign
  manager exists to automate.
- Treating verifier approval as authority to consume an irreversible holdout.
- Integrating candidate source before its authorized holdout passes.
