# Iteration 004 analysis

Targets: fix the two defects proven by live protocols 0.3.2 verification.

1. Explicit `--trust-codex-hooks` consent must be able to authorize the exact
   two active protocols handlers when Codex reports them as `enabled=false`
   and `trustStatus=modified`. Exact plugin, key, event, active-cache source,
   Windows command, and `currentHash` validation remain mandatory. Without the
   consent flag, installation must fail clearly and perform no trust write.
2. The exact-active-handler unit fixture must control its active plugin root
   so a real 0.3.2 cache cannot override the temporary source root. Production
   active-cache selection and validation remain unchanged.

TDD acceptance: adjust the existing installer authorization contract to begin
with both protocols handlers disabled and modified, prove that the consent path
is red before implementation, and isolate the existing compatibility fixture
with a mock of `active_codex_plugin_root`.

The required red run executed the disabled-upgrade authorization test alone. It
failed because `codex_hook_hashes_for_authorization` rejected the disabled
SessionStart handler as inexact before installation could issue the required
`--trust-codex-hooks` refusal.

Implementation result:

- Authorization hash discovery still validates the exact two protocols keys,
  events, command handlers, plugin identity, active-cache manifest paths,
  Git-for-Windows commands, and Codex-owned SHA-256 hashes, but permits their
  current enabled state to be false.
- Both the already-authorized fast path and the post-write verification now
  require every protocols key to be enabled and trusted. The existing batch
  write remains limited to those two keys and writes `enabled=true` plus each
  returned `trusted_hash`.
- Without explicit consent, the disabled/modified fixture reaches the clear
  `--trust-codex-hooks` error and the test proves no authorization write occurs.
- The live-handler compatibility fixture mocks `active_codex_plugin_root` to
  its temporary plugin root. Production cache selection is unchanged.
- Protocols and profile remain 0.3.2 because no packaged plugin content
  changed.

Verification result: the focused suite passed all 13 contracts. The full
Git-for-Windows/MSYS `scripts/verify.sh` gate passed, including skill lint,
profile validation, actor-profile cases, experiment cases, live doctor, and
`git diff --check`. A separate `uv run scripts/install_skills.py doctor` passed
against installed protocols 0.3.2 with the Codex hook enabled, trusted, active,
and source/cache-integral. Native acceptance was not run.
