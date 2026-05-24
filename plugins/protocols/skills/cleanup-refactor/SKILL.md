---
name: cleanup-refactor
description: Deletion-first fixed-point protocol for refactors, cleanup, migrations, and architectural convergence. Use when replacing old surfaces, removing helper debt, shrinking code, moving ownership boundaries, or auditing every symbol in a slice.
disable-model-invocation: false
---

# Cleanup Refactor Protocol

Use when: refactoring, cleanup, migration completion, helper deletion,
ownership-boundary repair, code shrinkage, or fixed-point convergence toward a
target architecture.

## Core Rule

Cleanup is not an inventory. Cleanup is a fixed-point loop that deletes or
moves wrong production surfaces, lets gates expose remaining callers, and
repeats until the old surface cannot be found.

The desired final state controls the work. Passing tests, a plausible plan, or
a large audit table does not mean the cleanup is complete while wrong
production code still exists.

## Required Inputs

Before editing, identify:

- **Target architecture**: the exact owner, type, representation, or interface
  that should remain.
- **Forbidden surfaces**: old helpers, shims, aliases, fallback readers,
  duplicated metadata, loose payloads, compatibility branches, re-export
  paths, generated-by-hand models, or other surfaces that must not survive.
- **Slice boundary**: one bounded directory, package, file, family, or symbol
  group.
- **Search gates**: literal or structural searches that prove forbidden
  surfaces are gone from the slice.
- **Runtime gates**: tests, type checks, linters, benchmarks, or project gates
  that prove the rewritten callers use the target surface.
- **Record file**: a repo-local markdown file that records each fixed-point
  iteration.

If the target owner or forbidden surface can be discovered by reading the repo,
read it before editing. Do not turn discoverable uncertainty into an
implementation blocker.

## Ownership-Understanding Gate

Before choosing a disposition for a symbol or production surface, explain why it
exists and what kind of thing it is:

- family or charter-backed model;
- document or decoded IO shape;
- runtime domain object;
- semantic reference/type/value object;
- app or workflow owner surface;
- CLI/UI adapter;
- test fixture or scaffold;
- duplicate helper, compatibility path, or dead surface.

For every DTO, parser, payload, mapping, row, or `from_payload` surface, answer
whether the shape is already defined by a family, charter, document type, or
generic IO decoder. If it is, use that owner and delete the duplicate shape. If
it is not, decide whether the missing owner must be created in the correct
metadata layer or whether the surface is test-only/dead and should be deleted.

For every union alias, helper accessor family, loaded/document wrapper, or
`from_payload` helper, classify it before choosing a disposition:

- real domain type;
- IO boundary carrier;
- family/charter-backed document surface;
- compatibility alias hiding multiple representations;
- test scaffold.

If it is a compatibility alias, delete it first and force callers onto the real
owner API. If it is an IO boundary carrier, prove the boundary and prevent
decoded payloads from crossing into core runtime. If it is family/charter-backed,
use the family, charter, document, or generic decoder directly instead of a
local helper layer.

"Only tests use it" is not enough evidence for deletion. It may indicate dead
production code, but it may also be a boundary contract test for a missing or
misplaced owner. Read the relevant family, charter, document, and caller
surfaces before deciding.

## Fixed-Point Workflow

Run the loop on one bounded slice at a time.

1. State the literal requested outcome and the active slice.
2. Verify current branch and relevant dirty state.
3. Read the whole slice before deciding file disposition.
4. Pass the ownership-understanding gate for each symbol or production surface.
5. Decompose the slice by file first, then by actual symbol or production
   surface inside that file.
6. If any production class, function, helper, alias, shim, fallback, duplicate
   model, duplicated metadata, compatibility branch, or wrong owner surface in a
   file violates the target architecture, mark the whole file for deletion.
7. After deleting the file, use the breakage review to decide which capabilities
   are recreated in real owner files and which caller paths are deleted.
8. For each surviving symbol or surface in a file that passed the file-level
   deletion gate, choose exactly one disposition:
   - **delete**: remove it because the target architecture already owns the
     job or the behavior is not needed.
   - **move**: relocate it to the correct owner after verifying it is not
     already there.
   - **consolidate**: merge duplicate implementations into the single owning
     implementation, then delete the duplicates.
   - **rewrite**: replace the wrong representation with the target typed
     interface or owner API.
   - **keep**: leave it only when it is already in the correct owner, has no
     forbidden shape, and passes the slice gates.
9. Delete the wrong production file or surface first.
10. Use compiler, type, test, and search failures as the rethink queue.
11. For each remaining reference exposed by deletion, run the breakage review:
   - identify the capability the caller was getting from the deleted surface;
   - decide whether that capability should still exist;
   - if it should not exist, delete the caller path too;
   - if it should exist, identify the real owner that already owns it;
   - if no real owner exists, create the capability in the correct owner layer;
   - update the caller to that owner or remove it.
12. Run the slice search gates.
13. Run the smallest meaningful runtime gates.
14. Commit the kept reduction atomically.
15. Update the record file with the action, evidence, gates, commit, and next
    slice.
16. Repeat until the search gates and runtime gates produce no remaining work
    for the slice.

## Deletion-First Rule

When replacing an interface, representation, storage surface, helper family, or
identity surface:

- delete the old production surface first;
- do not add a wrapper, shim, alias, bridge, compatibility branch, fallback,
  renamed helper, adapter layer, or dual path;
- do not keep old and new APIs in parallel;
- do not convert old shapes into new shapes silently;
- do not preserve code because it is currently used when it should not be used;
- use the project-owned target API directly.

If a compatibility path is truly required, name the external constraint that
forces it. Code controlled by the current stack is not an external constraint.

## Breakage Review Rule

Deletion breakage is not an import-repair queue. It is a forced ownership and
existence review for every remaining reference.

For each compile, type, test, or search failure caused by deleting a surface,
answer these questions before editing the caller:

- What exact capability did the deleted surface provide here?
- Should that capability still exist in the target architecture?
- If no, what caller path is deleted with it?
- If yes, which existing owner already owns that capability?
- If no owner exists, which owner layer must be created or extended?
- What evidence proves the new owner is not a renamed copy of the deleted
  surface?

Allowed outcomes are deletion, direct use of an existing owner, or creation of
the missing owner in the correct layer. Forbidden outcomes are import-only
repair, moving a function under a new module name, reconstructing the deleted
module as a cleaner helper, or making tests pass by preserving the old
responsibility behind another spelling.

## Ownership Rule

Move behavior to the layer that owns the concept.

- Generic storage, schema, IO, reference, registry, placement, and session
  mechanics belong in the generic infrastructure layer.
- Product or domain repositories own semantic meaning, policy, and domain
  methods.
- CLI and UI layers adapt inputs and render outputs; they do not own reusable
  workflows or mutation semantics.
- Typed/domain objects cross runtime boundaries. Loose dictionaries, stringly
  IDs, and source-local handles stop at the IO or authoring boundary unless the
  target architecture explicitly says otherwise.

Do not duplicate field names, model fields, schema knowledge, or placement
rules outside the owner metadata. If the type system or metadata can carry the
fact, use that source of truth.

## Record Template

```markdown
# Cleanup Refactor Fixed-Point Log - YYYY-MM-DD

Target architecture:
- ...

Forbidden surfaces:
- ...

Search gates:
- `...`

Runtime gates:
- `...`

## Iteration N - `[slice]`

Slice read:
- `path`

Surfaces:
- `symbol_or_surface`
  - Disposition: delete | move | consolidate | rewrite | keep
  - Owner after cleanup: `...`
  - Action: ...
  - Evidence: ...

Gate results:
- Pass/Fail: `command`

Commit:
- `hash message`

Next slice:
- `...`
```

## Search Gates

Search gates should prove the old production surface is gone, not merely that a
class or function was renamed.

Good gates:

- exact old import path;
- exact old helper or adapter name;
- union aliases, helper accessor families, loaded/document wrappers, or
  `from_payload` helpers that hide multiple representations;
- field names or payload keys that should be metadata-driven;
- compatibility phrases such as `legacy`, `fallback`, `normalize`, `coerce`,
  `shim`, `adapter`, `old shape`, or `if old`;
- broad package imports that preserve convenience re-export surfaces;
- duplicated model, DTO, payload, or dictionary field definitions.

When a gate finds production code, the next action is another cleanup
iteration. Do not mark the slice complete.

## Commit Protocol

Commit each kept reduction before moving to a different slice.

Commit message body should name the active principles, for example:

```text
Governing principles:

- no old production surface survives through wrappers, aliases, adapters,
  fallbacks, compatibility branches, re-export modules, or renamed helpers;
- owner metadata and type APIs are the source of truth;
- domain repositories keep semantic behavior in the correct owner layer;
- runtime APIs receive typed/domain objects past the IO boundary;
- if the content fails those checks, it is deleted, moved, consolidated, or
  rewritten.
```

## Exit Criteria

The cleanup is complete only when:

- every symbol or production surface in the slice has a recorded disposition;
- forbidden search gates are zero-hit or each remaining hit is outside
  production scope and recorded;
- runtime gates pass;
- old and new production paths do not coexist;
- the record file names the next slice or states that the whole requested scope
  reached fixed point.

## Anti-Patterns

- Building a large inventory instead of deleting the first wrong surface.
- Saying "used" when the actual question is "should be used".
- Renaming a helper to dodge a search gate.
- Adding a generic-looking wrapper around a specific old path.
- Hand-writing fields, DTOs, or models that should come from metadata.
- Deleting or keeping a DTO/parser/payload surface before proving whether a
  family, charter, document type, or generic IO decoder already owns that shape.
- Carrying old input forward through coercion or normalization.
- Treating tests as completion while forbidden production surfaces remain.
- Calling a draft workstream executable while it still contains unresolved
  repo-discoverable decisions.
