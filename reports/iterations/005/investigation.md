# Iteration 005 native Codex lifecycle investigation

Date: 2026-07-11

Status: external Codex blocker; harness correction not attempted.

## Exact prior causal failure

The preserved failed stream is
`reports/codex-native-acceptance-failed-codex-native-1783778050-402.jsonl`.
It announced root thread `019f5175-1493-7cc1-b5e0-2050369255c4`, then Codex
wrote this diagnostic outside the JSON stream:

`collab spawn failed: no thread with id: 019f5175-1493-7cc1-b5e0-2050369255c4`

That is a `ThreadNotFound` failure for the announced root. There is no
`collab_tool_call` item, no receiver/child thread ID, and no child agent state
in the JSON events. Therefore no child existed. The only
`command_execution` item read the installed subagent skill in the parent; no
worker command was attempted. The final agent message itself says the spawn
failed and no worker ran.

The old harness merged stderr into JSON stdout and searched the resulting
bytes with raw `grep`. Distracting prompt and skill prose contains strings
such as `default`, `codex-scout`, `SubagentStart`, `SubagentStop`, and
`completed`, so those searches can produce false positives without any typed
lifecycle event. The preserved stream also begins with the non-JSON diagnostic
`Reading additional input from stdin...`; valid acceptance must reject such
stdout instead of treating it as JSONL.

Codex 0.144.1's
`codex-rs/exec/src/event_processor_with_jsonl_output.rs` maps completed native
collaboration calls to typed `collab_tool_call` items containing `tool`,
`sender_thread_id`, `receiver_thread_ids`, `agents_states`, and `status`.
It maps executed commands to typed `command_execution` items. The same
processor intentionally consumes `HookStarted` and `HookCompleted`
notifications without emitting JSON events. Its public event enum has no
`SubagentStart`, `SubagentStop`, or `SessionEnd` event variants. Acceptance
therefore cannot assert those notification names in exec JSON.

Ward's `guard.go` derives the exact family directory as
`%TEMP%/ward/families/<sha256(session key)>`; actor records live below its
`actors` directory. `DeleteActorState` removes one actor record, while
`DeleteSessionFamily` validates the family records and removes the entire
exact family. The failed run left the root Ward family in place, so cleanup was
not proved and the parent family leaked. Searching Ward state for a prompt
nonce is not an identity proof because the family is keyed by the actual root
thread/session ID, not prompt text.

## Required deterministic classification

The regression parser must classify the preserved stream, despite its
distracting prose, as:

- `spawn_failed=true`
- `worker_created=false`
- `allowed_command_observed=false`
- `denial_observed=false`
- `cleanup_unproved=true`

The repaired harness must keep stderr separate, reject non-JSON stdout, and
derive all positive worker claims from typed events plus the exact Ward family
for the announced root thread.

## Controlled A/B preregistration

Hypothesis: Codex 0.144.1 removes an ephemeral root from the collaboration
thread manager before `spawn_agent`, while the otherwise identical persistent
root remains available and can create a default worker.

Single variable: presence versus absence of `codex exec --ephemeral`.

Primary gate: the non-ephemeral run must emit a successful completed
`spawn_agent` `collab_tool_call` with a concrete receiver thread ID. The
ephemeral run must reproduce the root `ThreadNotFound` failure. Root/child IDs,
JSON stdout, stderr, exact Ward family paths/states, and post-exit cleanup are
recorded separately for both arms.

Kill criterion: if the non-ephemeral arm does not prove successful default
worker creation, stop with an external Codex blocker. Do not weaken native
acceptance or change unrelated source.

## Controlled A/B result

Raw evidence is preserved under `reports/iterations/005/ephemeral-ab/`. Both
arms exited 0 and kept stderr separate from JSON stdout. The single input
variable was `--ephemeral`:

| Arm | Root thread | Ward child actor | Exact Ward family |
| --- | --- | --- | --- |
| ephemeral | `019f5189-ddb8-7320-aaf9-302919fb6f9b` | `019f518a-33ba-7923-a999-6602164cdd16` | `/tmp/ward/families/5a585b9ad1d092566eb0b9cd3dd33ebaf8220f27a5b9d5de5b266d272995ed40` |
| persistent | `019f518a-c1c4-78e3-a35a-b2ebf8996155` | `019f518b-16b0-72f2-8b8f-1b4996f117a1` | `/tmp/ward/families/77b5bf656bcf34833e257ec8c74e8ceabbbe36fcc80421e0f952d555e7ed8a22` |

Each live Ward snapshot contains exactly the corresponding child record with
`agent_type="default"`, `phase="codex-scout"`, and `history=["Bash"]`. That
proves a child hook ran in both arms and allowed the gate-probing Bash command.
It does not satisfy the exec JSON acceptance contract.

Neither arm emitted a `spawn_agent` `collab_tool_call`. Neither arm emitted a
worker `command_execution`. Their only collaboration JSON items were empty
completed `wait` calls. Stderr contained only
`Reading additional input from stdin...`; no `ThreadNotFound` occurred in this
A/B. After each Codex parent exited, the exact root family and child actor JSON
still existed. Thus the A/B also directly proves cleanup failure in both arms.

## Blocker decision

Removing `--ephemeral` did not produce the preregistered successful completed
`spawn_agent` item with a concrete receiver ID. It therefore did not prove
successful default-worker spawn through the supported Codex 0.144.1 exec JSON
interface. The single-variable hypothesis is falsified: ephemeral and
persistent behavior were equivalent on the required evidence surface.

The external Codex blocker is exact: native collaboration can create a Ward
default-worker actor, but Codex 0.144.1 exec JSON omits the corresponding
`spawn_agent` and child command items and both process modes leak the actual
root Ward family after exit. Protocols-owned parsing cannot reconstruct those
missing typed events without weakening acceptance. Per the kill criterion, no
change was made to `scripts/codex_native_worker_acceptance.sh`, Codex source,
Ward source, plugin content, or version metadata. Native acceptance remains
blocked.
