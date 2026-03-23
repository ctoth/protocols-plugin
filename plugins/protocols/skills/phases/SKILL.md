---
name: phases
description: Orchestrate multi-phase workflows with parallel and sequential stages. Research, plan, implement, verify — each phase produces filesystem artifacts consumed by the next. Use when task decomposes into stages that would overflow a single agent's context.
disable-model-invocation: true
---

# Workflow Phases Protocol

Use when: task decomposes into research/plan/implement/verify stages, context would overflow with full problem, want debuggable intermediate artifacts. Always dispatch via general-purpose agents with prompt files, never Explore/Plan agents.

## Core Concept

Orchestrate via filesystem artifacts. No agent-to-agent communication. Foreman reads/writes the "message bus" (docs/).

## Phase Types

### PARALLEL phases
- Agents work independently
- No coordination overhead
- Output to separate files
- Use for: research, independent module implementation, test writing

**Good parallel tasks** (per Simon Willison):
- Research/exploration (multiple topics at once)
- Documentation of existing code
- Fixing deprecation warnings
- Proof of concepts / spikes
- Test writing for independent modules

**Bad parallel tasks**:
- Anything touching the same files
- Tasks requiring coordination decisions
- Implementation with unclear boundaries

### SEQUENTIAL phases
- Single agent synthesizes prior phase output
- Reads multiple inputs, produces unified output
- Use for: planning, integration, conflict resolution

## Standard Sequence

```
[Research]       PARALLEL   -> docs/reports/*.md
[Planning]       SEQUENTIAL -> docs/plans/*.md (reads reports/)
[Implementation] PARALLEL   -> src/* (reads plans/)
[Verification]   SEQUENTIAL -> test results
[Integration]    SEQUENTIAL -> final assembly
```

## Directory Convention

```
docs/
├── reports/    # Research output (consumed by planners)
├── plans/      # Planning output (consumed by implementers)
└── notes/      # Decisions, context, working docs
```

## Agent Prompt Template

```markdown
You are a [ROLE] agent.

INPUT: Read [FILE_PATHS]
TASK: [SPECIFIC_TASK]
OUTPUT: Write findings to [OUTPUT_PATH]

Constraints:
- Stay focused on [DOMAIN]
- Do not implement outside your scope
- Note blockers/dependencies for foreman
```

## Phase Diagram Example

```
[Research Phase] - PARALLEL
    ├── Domain A Research -> docs/reports/domain-a.md
    ├── Domain B Research -> docs/reports/domain-b.md
    └── Domain C Research -> docs/reports/domain-c.md
              │
              v
[Planning Phase] - SEQUENTIAL
    └── Planner (reads all reports) -> docs/plans/implementation-plan.md
              │
              v
[Implementation Phase] - PARALLEL where possible
    ├── Module A -> src/module_a/
    ├── Module B -> src/module_b/
    └── Tests -> tests/
              │
              v
[Integration Phase] - SEQUENTIAL
    └── Integration (final assembly, testing)
```

## When to Use

- Task decomposes into independent subtasks
- Context window would overflow with full problem
- Want debuggable intermediate artifacts
- Multiple research domains before synthesis

## Benefits

- Scalability: more agents = more parallelism
- Clean context: each agent gets fresh context
- Debuggability: all intermediate artifacts in files
- Resumability: can restart from any phase

## Anti-patterns

- Agents needing real-time coordination (use sequential)
- Foreman doing substantive work (delegate)
- Skipping planning phase (implementation diverges)
- Not reading prior phase outputs before starting next phase
