# Iteration 002 analysis

Target: make the Codex installer and doctor own the native
`protocols@protocols-marketplace` lifecycle independently from Claude while
preserving the existing Codex skill-link installation.

Live failure cause: Codex had native plugin version 0.2.0 installed from this
local repository, but its cached hook manifest contained only `SessionStart`
and no `ward-role.sh`. The user `SubagentStart` hook chain contained only
Claudio, so Ward lazily created the first worker actor as `uninitialized` and
correctly denied its first Bash call. The installer managed Codex skill links
only, and doctor inferred lifecycle health solely from Claude settings and the
Claude plugin version.

TDD acceptance: first add unit coverage for Codex plugin-list JSON parsing,
installed/enabled/exact-version checks, the cached/source `SubagentStart`
`ward-role.sh` manifest, and stale-install remove-then-add behavior through the
existing command runner seam. Run this focused suite red before implementation.

The first red run had one error and one failure: the parser/checker did not
exist, and the Codex install path issued no native plugin commands. After that
implementation passed all nine focused tests, the first live installer run
exposed a Windows-only runner gap: Python could not execute the bare extensionless
`codex` shim. The install-flow test was tightened to require resolved
`codex.cmd`, failed red, then passed after adding the smallest direct executable
resolution alongside the existing runner seam.

Result: `install --platform codex` intentionally removed the installed 0.2.0
plugin and added 0.3.1, while continuing the existing Codex skill-link flow.
The installed 0.3.1 cache contains `SubagentStart -> ward-role.sh`; Claude
remained enabled at 0.3.1. All nine focused unit tests and the unchanged full
`scripts/verify.sh` gate passed. The live native spawn acceptance remains a
separate post-commit check after restarting Codex.
