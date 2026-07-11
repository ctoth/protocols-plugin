# Iteration 006 analysis

Target: repair native Codex collaboration initialization without weakening the
missing/unknown Claude fail-closed boundary.

The focused red run executed 36 policy cases. Thirty-five passed. The exact
native Codex omitted-type payload, including the required Codex `turn_id`
extension, remained uninitialized and failed its allowed `rg --files` case.
Its harmless write remained denied. Existing missing and unknown Claude cases
also remained denied, establishing the boundary the fix must preserve.

The selected owner is `plugins/protocols/hooks/ward-role.sh`. Ward's lifecycle
commands are host-neutral state primitives, while the protocols hook already
owns the host-role-to-phase mapping. No Ward or Codex source change is needed.

The green focused run passed all 36 policy cases. The full repository gate and
doctor passed with Codex, Claude, and the Ward profile all at `0.3.3`.

The required live app-server acceptance did not complete in two consecutive
bounded attempts. The second preserved run positively observed root thread
`019f51ac-6a92-7120-88fc-6728f3aacd6e`, child thread
`019f51ac-f724-7730-bf13-6797eb5b4f83`, a completed protocols `SubagentStart`
hook from the installed `0.3.3` cache, repeated successful child `rg --files`
executions, Ward phase `codex-scout` for that exact actor, and Codex's exact
stderr record that Ward blocked the child's harmless `Set-Content`. The
release gate nevertheless did not fire, so the worker could not return and
the harness could not prove exact actor/session cleanup. Per the exact-
convergence rule, no third harness slice was attempted.
