---
name: external-agents
description: Use Codex and Gemini CLIs as external reviewers for gated review chunks. They read prompt files and write reports. Use for pre-implementation review, spec validation, architecture critique, or second opinions.
disable-model-invocation: false
allowed-tools:
  - Read
  - Bash
  - Write
---

# External CLI Reviewers/Agents (Codex / Gemini)

Use Codex and Gemini CLIs as external reviewers for gated review chunks. They read prompt files and write reports.

## When to Use

- **Before major implementation**: Get external review of spec changes, architecture decisions
- **After spec updates**: Validate changes before implementing code
- **Gated review chunks**: When plan specifies external review gate
- **Second opinion**: When uncertain about approach

## Codex (Preferred - more reliable)

```bash
codex exec --dangerously-bypass-approvals-and-sandbox "Read prompts/task.md and write report to reports/task-report.md"
```

- `--dangerously-bypass-approvals-and-sandbox` enables writes (required)
- Codex correctly interprets and executes instructions
- Use for: code review, spec validation, architecture critique

## Gemini (Secondary - less reliable for execution)

```bash
gemini --yolo "Read prompts/task.md and write report to reports/task-report.md"
```

- `--yolo` auto-approves all actions
- May copy files instead of executing instructions - verify output
- Use for: second opinion after Codex, simple reviews

## Workflow Pattern

1. Write prompt to `prompts/review-task.md` with clear instructions
2. Run Codex (primary): `codex exec --dangerously-bypass-approvals-and-sandbox "Read prompts/review-task.md and write report to reports/codex-task-report.md"`
3. Optionally run Gemini: `gemini --yolo "Read prompts/review-task.md and write report to reports/gemini-task-report.md"`
4. Check `reports/` for outputs
5. Gate: If issues found, iterate before proceeding

## Prompt Template

```markdown
# Review Task: [Title]

## Context
[What's being reviewed and why]

## Files to Review
- `path/to/file1.md`
- `path/to/file2.yml`

## Questions to Answer
1. [Specific question]
2. [Specific question]

## Output
Write your review to `reports/[name]-report.md` with:
- Summary of findings
- Issues identified (if any)
- Recommendations
```
