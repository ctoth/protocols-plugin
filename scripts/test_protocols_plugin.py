#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Focused contract tests for actor-scoped Ward integration."""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def load_installer():
    path = ROOT / "scripts" / "install_skills.py"
    spec = importlib.util.spec_from_file_location("install_skills", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ActorScopedWardContractTest(unittest.TestCase):
    def test_plugin_and_profile_versions_are_coherent(self) -> None:
        manifest = json.loads(
            (ROOT / "plugins/protocols/.claude-plugin/plugin.json").read_text(
                encoding="utf-8"
            )
        )
        profile = (ROOT / "plugins/protocols/ward-profile/profile.yaml").read_text(
            encoding="utf-8"
        )
        self.assertEqual(manifest["version"], "0.3.0")
        self.assertIn("version: 0.3.0", profile)
        self.assertIn("actor-scoped-protocol-phases", profile)

    def test_subagent_start_hook_initializes_explicit_roles(self) -> None:
        hooks = json.loads(
            (ROOT / "plugins/protocols/hooks/hooks.json").read_text(encoding="utf-8")
        )["hooks"]
        commands = [
            hook["command"]
            for group in hooks["SubagentStart"]
            for hook in group["hooks"]
        ]
        self.assertEqual(commands, ["${CLAUDE_PLUGIN_ROOT}/hooks/ward-role.sh"])

        role_hook = (ROOT / "plugins/protocols/hooks/ward-role.sh").read_text(
            encoding="utf-8"
        )
        for role in (
            "scout",
            "coder",
            "analyst",
            "verifier",
            "researcher",
            "adversary",
            "experiment-worker",
        ):
            self.assertIn(role, role_hook)
            self.assertIn(f"protocols:{role}", role_hook)
        self.assertIn('"$WARD_BIN" set', role_hook)
        self.assertIn("--hook-input", role_hook)
        self.assertIn('"$WARD_BIN" start-actor', role_hook)
        self.assertNotIn("--session", role_hook)

    def test_uninitialized_workers_fail_closed(self) -> None:
        rule = (
            ROOT
            / "plugins/protocols/ward-profile/rules/uninitialized-worker-gate.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn('session.phase == "uninitialized"', rule)
        self.assertIn('tool in ["Bash", "Edit", "Write"]', rule)
        self.assertIn("role initialization", rule)

    def test_experiment_worker_agent_is_explicit(self) -> None:
        agent = (ROOT / "plugins/protocols/agents/experiment-worker.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("name: experiment-worker", agent)
        self.assertIn("ward actor phase", agent.lower())
        self.assertNotIn("ward set experiment-worker", agent)

    def test_doctor_owns_live_compatibility_checks(self) -> None:
        installer = load_installer()
        self.assertEqual(
            installer.REQUIRED_WARD_REVISION,
            "fb526ae936ce4715256d23c277ddec448359c598",
        )
        self.assertEqual(installer.REQUIRED_PROTOCOLS_VERSION, "0.3.0")
        self.assertTrue(callable(installer.check_ward_compatibility))
        self.assertTrue(callable(installer.check_claude_plugin_compatibility))
        marketplace = installer.ClaudeMarketplace(
            name="protocols-marketplace",
            path=Path("marketplace.json"),
            plugins=(installer.ClaudePlugin(name="protocols"),),
        )
        stale = [
            {
                "plugin": "protocols@protocols-marketplace",
                "version": "0.1.2",
                "scope": "user",
                "status": "enabled",
            }
        ]
        current = [
            {
                "plugin": "protocols@protocols-marketplace",
                "version": "0.3.0",
                "scope": "user",
                "status": "enabled",
            }
        ]
        self.assertIn("0.1.2", installer.check_claude_plugin_compatibility(stale, marketplace)[0])
        self.assertEqual(
            installer.check_claude_plugin_compatibility(current, marketplace), []
        )

    def test_actor_smokes_and_real_acceptance_harness_are_present(self) -> None:
        profile_smoke = (ROOT / "scripts/ward_profile_verify.sh").read_text(
            encoding="utf-8"
        )
        experiment_smoke = (ROOT / "scripts/experiment_gate_smoke.sh").read_text(
            encoding="utf-8"
        )
        acceptance = (ROOT / "scripts/ward_actor_acceptance.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("agent_id", profile_smoke)
        self.assertIn("uninitialized", profile_smoke)
        self.assertIn("experiment-worker", experiment_smoke)
        self.assertIn("agent_id", experiment_smoke)
        self.assertIn("claude", acceptance)
        self.assertIn("--include-hook-events", acceptance)
        self.assertIn("scout", acceptance)
        self.assertIn("experiment-worker", acceptance)
        self.assertIn("parallel", acceptance.lower())
        self.assertIn("ward.exe set foreman", acceptance)
        self.assertIn("ward: phase", acceptance)
        self.assertIn("unset CODEX_THREAD_ID WARD_SESSION WARD_ACTOR_ID", acceptance)
        self.assertIn("PARENT_FOREMAN_DENIAL_OK", acceptance)
        self.assertIn("cleanup_fixture", acceptance)
        self.assertIn("ward-actor-acceptance-$NONCE.md", acceptance)
        self.assertIn("ward-actor-acceptance", acceptance)
        self.assertIn("FIXTURE_LOCK", acceptance)


if __name__ == "__main__":
    unittest.main()
