# Iteration 005 analysis

Target: repair native Codex lifecycle acceptance only if a controlled
`--ephemeral` A/B proves the protocols-owned cause.

The preserved failure was first converted into a deterministic typed parser
regression. Its initial red run executed 2 tests and produced 2 errors because
the parser did not exist. The implemented parser rejects non-JSON stdout and
does not treat prompt, skill, or final-message prose as lifecycle evidence.
The focused green run executed 3 tests and passed. It classifies the preserved
failure as spawn failed, no worker created, no allowed worker command, no Ward
denial, and cleanup unproved. It also classifies the live persistent A/B arm as
no proven worker despite the separate Ward actor snapshot.

The controlled A/B changed only the `--ephemeral` argument. Both arms created
a physical-gate-held Ward actor with the exact default-worker state, but
neither emitted a completed `spawn_agent` JSON item or any child command JSON
item. Both exact root Ward families remained after parent exit. The persistent
arm therefore failed the preregistered proof gate and falsified the proposed
cause.

Per the task's kill condition, the live harness was not changed. No installed
plugin refresh or metadata update is required because packaged plugin source
is unchanged. Native acceptance remains blocked by the installed Codex 0.144.1
exec JSON/lifecycle behavior recorded in `investigation.md` and its raw A/B
artifacts.
