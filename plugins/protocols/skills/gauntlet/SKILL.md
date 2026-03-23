---
name: gauntlet
description: Four-role sequential pipeline for complex, high-risk changes. Scout surveys the codebase, Coder implements with TDD, Analyst finds problems, Verifier gates the merge. Use for large refactors, architectural shifts, and interdependent multi-phase work.
disable-model-invocation: true
---

# Gauntlet Protocol

Use when: complex, multi-phase, interdependent work where each phase builds on the previous. High-risk changes. Large refactors. Architectural shifts.

Do NOT use for: simple fixes, independent parallel tasks, straightforward test additions.

## Four Roles, Sequential

**Scout -> Coder -> Analyst -> Verifier**

| Role | Job | Key instruction |
|------|-----|-----------------|
| Scout | Survey codebase, find patterns | "Do NOT implement" |
| Coder | Implement with TDD | "RED -> GREEN -> REFACTOR. All three." |
| Analyst | Find problems | "Your job is to find problems, not approve" |
| Verifier | Final gate | "Default is NO-MERGE. Code must earn it." |

## Flow

1. Scout finds how -> Coder implements -> Analyst reviews -> Verifier decides
2. **MERGE**: Done
3. **NO-MERGE**: Revert, update scout prompt with learnings, iterate

## Coder Rules

**Must do full TDD:**
- RED: Write failing test
- GREEN: Make it pass
- REFACTOR: Extract abstractions, clean up — **this is not optional**

**Cannot deviate from plan:**
- Coders implement the plan. They do not decide the plan is wrong.
- If coder believes plan is flawed: STOP, write objection to report, exit
- "Pragmatic shortcuts" are deviations. Deviations are failures.

Include this in EVERY coder prompt:

```
## HARD CONSTRAINT: No Deviation

You implement the plan exactly as specified. You do not have authority to change the architecture.

If you believe the plan is wrong:
1. STOP immediately
2. Write your objection to reports/{task}-coder.md
3. Exit without implementing anything

You are NOT authorized to:
- Choose a "more pragmatic" approach
- Implement a partial solution
- Rationalize why the plan should be different

Implement the plan or report why you cannot. There is no third option.
```

## Analyst Checks

- Edge cases, security, race conditions, error handling
- Tests cover failure modes, not just happy path
- Architecture: proper abstraction or inline spaghetti?

## Verifier Rejects If

- Tests fail
- Analyst found major/blocker issues
- Missing error handling or security concerns
- No proper abstraction (code dumped inline)

Foreman only reads verifier verdict. Don't read scout/analyst reports yourself.
