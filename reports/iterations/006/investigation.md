# Investigation: native Codex omitted `agent_type`

Date: 2026-07-11

## Facts (verified)

- A real parent-platform collaboration worker reached `PreToolUse` with a stable actor ID, but its preceding `SubagentStart` omitted `agent_type`; the protocols hook initialized only an uninitialized Ward actor and Ward denied the first `rg` command.
- Installed `codex --version` is `codex-cli 0.144.1` from the global `@openai/codex@0.144.1` package.
- The exact `rust-v0.144.1` source defines `SubagentStartCommandInput.turn_id` as a required string and labels it a Codex extension in `codex-rs/hooks/src/schema.rs`.
- The same tag constructs native `SubagentStart` input in `codex-rs/hooks/src/events/session_start.rs` with `turn_id`, `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `model`, `permission_mode`, `agent_id`, and `agent_type`.
- The same tag's `hook_runtime.rs` normalizes an absent thread-spawn role to `default`; the parent-platform observation nevertheless proves that not every native collaboration integration supplies that normalized field to the plugin hook.
- Claude Task `SubagentStart` payloads use the shared Claude hook shape and do not contain Codex's `turn_id` extension. Existing deterministic fixtures exercise explicit Claude roles, unknown Claude roles, and a missing Claude role without `turn_id`.
- Ward's lifecycle entrypoints in `C:/Users/Q/code/ward/main.go` intentionally parse only session identity, actor identity, and role metadata. They do not own host detection for `SubagentStart`.

## Theories (plausible)

1. The protocols hook can safely recognize native Codex lifecycle input by a non-empty string `turn_id`; this predicts an omitted-type payload with `turn_id` should map to `codex-scout`, while the same omission without `turn_id` remains uninitialized.
2. Ward must normalize a Codex-specific event before protocols sees it; this predicts Ward has or needs a Codex lifecycle adapter for this flat `SubagentStart` shape.
3. No authoritative discriminator survives into hook stdin; this predicts source and diagnostic capture expose only fields shared with Claude.

## Tests Run

| Test | Hypothesis | Result | Rules Out | Supports |
| --- | --- | --- | --- | --- |
| Inspect installed version and exact `rust-v0.144.1` hook schema/construction | 1, 3 | `turn_id` is a required Codex extension on native start input | 3 | 1 |
| Inspect Ward lifecycle parsing | 2 | Ward deliberately performs host-neutral identity/state updates | Ward ownership | 1 |
| Add exact omitted-type native fixture with `turn_id` plus missing/unknown Claude fixtures and run `ward_profile_verify.sh` | 1 | Native fixture remained uninitialized and its `rg` was denied; missing/unknown Claude stayed denied | Current hook behavior is sufficient | 1 |

## Current Best Theory

The protocols hook owns the mapping. A non-empty string `turn_id` is the safe, source-defined Codex discriminator. Only the conjunction of missing `agent_type` and that field may map to `codex-scout`; mapping every missing type would violate fail-closed Claude behavior.

## Open Questions

- Why the acceptance process did not enter its direct Ward-denial/release branch after the preserved stream contained each prerequisite signal.

## Next Action

Stop live-harness iteration after two consecutive bounded failures. Preserve a
curated record of the typed app-server events, exact Ward actor state, and Codex
stderr denial as the blocker record; do not weaken the cleanup requirement or
attempt a third harness variant in this iteration.

## Live acceptance blocker

The supported app-server interface did expose authoritative child identity and
command ownership. In the second run:

- `item/completed` `subAgentActivity(kind=started)` identified child
  `019f51ac-f724-7730-bf13-6797eb5b4f83` under root
  `019f51ac-6a92-7120-88fc-6728f3aacd6e`.
- `hook/completed` identified the installed protocols `0.3.3`
  `SubagentStart` for that same child.
- `item/completed` recorded successful `rg --files` executions on that same
  child thread.
- `typed-evidence.json` records the same Ward actor at `phase=codex-scout` and
  Codex blocking the exact harmless `Set-Content` via the PreToolUse hook with
  Ward's native discovery denial reason.

The harness never created its release marker, so the held worker never
returned and exact actor/session cleanup was not observable. Both live runs
hit the six-minute timeout. This leaves one required acceptance failure.
