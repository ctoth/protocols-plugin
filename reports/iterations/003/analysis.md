# Iteration 003 analysis

Target: fix the proven native Codex hook defect without adding a duplicate
user-owned role hook. The protocols plugin must supply explicit Git-for-Windows
`sh.exe`/`cygpath` commands, authorize only its two active plugin-hook hashes
after explicit installer consent, and make doctor judge the effective live
`hooks/list` state independently from source/cache integrity.

Facts carried from the completed investigation:

- Codex 0.144.1 discovers both plugin hooks from `hooks/hooks.json`.
- The live `SubagentStart` handler was enabled but untrusted and therefore was
  excluded from the runnable handler set.
- A bare `.sh` command would be executed through PowerShell on Windows after
  trust, so the manifest requires `commandWindows` using `sh.exe` and
  `cygpath`; bare `bash.exe` is not acceptable.
- Codex owns normalized hook hashes. Installation must read `currentHash` from
  `hooks/list` and write those exact values through `config/batchWrite` only
  after `--trust-codex-hooks` authorization.
- Deterministic tests and live listing do not replace a fresh native default
  worker acceptance run. This worker will add the harness but will not refresh
  or trust the live plugin.

TDD acceptance: first replace the manifest-only doctor test with live-state
cases, require exact two-key authorization, require both Windows command
overrides and Windows POSIX-shell prerequisites, and require a distinct native
Codex acceptance harness with the investigation's lifecycle invariants. Run the
focused suite red before implementation.

The required red run executed 12 tests: 3 passed and 9 failed/errored. The
failures covered every intended missing surface: both `commandWindows`
declarations, live exact-handler validation, two-key trust authorization,
Windows prerequisites, Codex Ward lifecycle validation, version/revision
invariants, and the separate native acceptance file.

Implementation result:

- Both POSIX commands remain unchanged and both handlers now use explicit
  `sh.exe -lc` plus `cygpath` Windows overrides.
- The installer performs a fresh initialized app-server exchange, obtains the
  two active hashes from `hooks/list`, requires `--trust-codex-hooks`, writes
  only those keys through `config/batchWrite`, and re-queries both handlers.
- Doctor independently reports plugin metadata, source/cache bytes, Windows
  prerequisites, the complete user Codex Ward lifecycle chain, and the exact
  effective cached `SubagentStart` handler state.
- The compatibility set is protocols/profile 0.3.2 plus clean Ward revision
  `cea6f35bdc4dea1180f2bb879dcb3a66f430795d`.
- `scripts/codex_native_worker_acceptance.sh` is a separate fresh-process paid
  release gate and contains no plugin refresh, trust write, or manual role
  transition.

Verification result: 13 focused contracts pass. The Git/MSYS repository gate
passes focused tests, skill lint, profile validation, 34 actor-profile cases,
and the experiment smoke, then intentionally stops at live doctor because this
worker did not refresh/trust the installed native plugins. The live evidence is
precise: Claude and Codex remain installed at 0.3.1; Codex's cached role command
is the old bare `.sh` form, its exact handler is untrusted, and its cache differs
from the new source manifest. The separate verifier must run the explicit
installer against this commit, restart Codex, rerun the full gate, and execute
the native acceptance harness.
