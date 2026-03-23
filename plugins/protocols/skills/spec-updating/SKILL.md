---
name: spec-updating
description: Spec update workflow with discovery, drafting, external review gates (Codex + Gemini), and integration phases. Use when adding, modifying, or extending specification documents. Specs are truth — code implements specs, never the reverse.
disable-model-invocation: true
---

# Spec-Updating Protocol

Use when: Adding, modifying, or extending specification documents.

## Core Principle

**Specs are truth. Code implements specs. Never the reverse.**

If you're about to write code that should be spec-backed, STOP and update the spec first.

## Protocol Phases

### Phase 1: Discovery

Before writing anything, understand what exists.

**Subagent dispatch:**
```
Task: Find all specs related to {feature}
- Search the spec directory for mentions of {keywords}
- List cross-references that might need updating
- Identify which spec file(s) should be modified
Output: reports/spec-discovery-{feature}.md
```

**Gate:** Must complete discovery before drafting.

### Phase 2: Draft

Write spec changes to a draft file, NOT directly to the spec directory.

**Location:** `prompts/spec-draft-{feature}.md`

**Draft template:**
```markdown
# Spec Draft: {Feature Name}

## Target File
{path to spec file}

## Section to Add/Modify
{section name}

## Proposed Content
{actual spec content - written as if it were in the spec}

## Cross-References
- {list of other specs that reference or are referenced by this}

## Open Questions
- {any unresolved design questions}
```

**Gate:** Draft must be complete before review.

### Phase 3: Codex Review Gate

External review by Codex CLI.

**Prompt file:** `prompts/review-spec-{feature}.md`
```markdown
# Review Task: Spec Draft for {Feature}

## Files to Read
- `prompts/spec-draft-{feature}.md` - The draft to review
- `{path to existing spec}` - The existing spec
- {any related specs from discovery}

## Review Criteria
1. Does the draft follow existing spec conventions?
2. Is it consistent with related specs?
3. Are cross-references correct?
4. Is terminology consistent?
5. Are there any contradictions with existing content?

## Output
Write review to `reports/codex-spec-review-{feature}.md`
Include: APPROVE, CONCERNS, or REJECT with explanation
```

**Command:**
```bash
codex exec --dangerously-bypass-approvals-and-sandbox \
  "Read prompts/review-spec-{feature}.md and follow its instructions"
```

**Gate:** Must be APPROVE or CONCERNS addressed before proceeding.

### Phase 4: Gemini Review Gate

Second opinion from Gemini CLI.

**Use same prompt file or create variant.**

**Command:**
```bash
gemini --yolo "Read prompts/review-spec-{feature}.md and follow its instructions. Write to reports/gemini-spec-review-{feature}.md"
```

**Gate:** Must be APPROVE or CONCERNS addressed before proceeding.

### Phase 5: Integration

Merge the draft into the actual spec file.

**Actions:**
1. Read current spec file
2. Find insertion/modification point
3. Apply changes from draft
4. Update any cross-references in other specs
5. Update glossary if new terms introduced

**Verification:**
- Spec file renders correctly (no broken markdown)
- Cross-reference links work
- No duplicate section headers

### Phase 6: Verification

Final verification that spec integrates properly.

**Subagent dispatch:**
```
Task: Verify spec integration for {feature}
- Check spec file renders correctly
- Verify cross-references resolve
- Check glossary has all new terms
- Verify no conflicts with project principles
Output: reports/spec-verification-{feature}.md
```

**Gate:** Must pass before implementation begins.

---

## Anti-Patterns

| Wrong | Right |
|-------|-------|
| Edit spec directly without review | Draft -> Review -> Merge |
| Skip discovery phase | Always discover related specs first |
| Implement then spec | Spec then implement |
| Single reviewer | Codex AND Gemini review |
| Inline draft in chat | Physical draft file |

## Checklist

- [ ] Discovery complete, related specs identified
- [ ] Draft written to prompts/spec-draft-{feature}.md
- [ ] Codex review passed or concerns addressed
- [ ] Gemini review passed or concerns addressed
- [ ] Draft merged to spec directory
- [ ] Cross-references updated
- [ ] Glossary updated (if needed)
- [ ] Verification passed
