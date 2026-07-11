#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Focused contract tests for actor-scoped Ward integration."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


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
        self.assertEqual(manifest["version"], "0.3.1")
        self.assertIn("version: 0.3.1", profile)
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
        self.assertIn("default) phase=codex-scout", role_hook)
        self.assertNotIn("--session", role_hook)

    def test_native_codex_scout_is_mechanically_read_only(self) -> None:
        rule = (
            ROOT
            / "plugins/protocols/ward-profile/rules/codex-scout-gate.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn('session.phase == "codex-scout"', rule)
        self.assertIn('tool in ["Edit", "Write"]', rule)
        self.assertIn('c.name == "rg"', rule)
        self.assertIn('c.git_category == "query"', rule)
        self.assertIn(
            'c.git_subcommand in ["status", "diff", "log", "show", "rev-parse"]',
            rule,
        )
        self.assertIn('size(input.commands) > 0', rule)
        self.assertIn('input.command.matches', rule)

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
        self.assertEqual(installer.REQUIRED_PROTOCOLS_VERSION, "0.3.1")
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
                "version": "0.3.1",
                "scope": "user",
                "status": "enabled",
            }
        ]
        self.assertIn("0.1.2", installer.check_claude_plugin_compatibility(stale, marketplace)[0])
        self.assertEqual(
            installer.check_claude_plugin_compatibility(current, marketplace), []
        )

    def test_codex_plugin_json_requires_current_enabled_role_hook(self) -> None:
        installer = load_installer()
        plugin_id = "protocols@protocols-marketplace"
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_root = Path(temp_dir)
            hooks_dir = plugin_root / "hooks"
            hooks_dir.mkdir()
            manifest_path = hooks_dir / "hooks.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "hooks": {
                            "SubagentStart": [
                                {
                                    "hooks": [
                                        {
                                            "command": (
                                                "${CLAUDE_PLUGIN_ROOT}/hooks/ward-role.sh"
                                            )
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            current_json = json.dumps(
                {
                    "installed": [
                        {
                            "pluginId": plugin_id,
                            "version": "0.3.1",
                            "installed": True,
                            "enabled": True,
                            "source": {"path": str(plugin_root)},
                        }
                    ]
                }
            )
            current = installer.parse_codex_plugin_list(current_json)
            self.assertEqual(installer.check_codex_plugin_compatibility(current), [])

            variants = (
                ([], "is not installed"),
                ([{**current[0], "enabled": False}], "not enabled"),
                ([{**current[0], "version": "0.2.0"}], "0.2.0"),
            )
            for entries, message in variants:
                with self.subTest(message=message):
                    self.assertIn(
                        message,
                        installer.check_codex_plugin_compatibility(entries)[0],
                    )

            manifest_path.write_text(
                json.dumps({"hooks": {"SessionStart": []}}), encoding="utf-8"
            )
            self.assertIn(
                "SubagentStart",
                installer.check_codex_plugin_compatibility(current)[0],
            )
            self.assertIn(
                "ward-role.sh",
                installer.check_codex_plugin_compatibility(current)[0],
            )

    def test_codex_install_refreshes_stale_native_plugin(self) -> None:
        installer = load_installer()
        plugin_id = "protocols@protocols-marketplace"
        stale_json = json.dumps(
            {
                "installed": [
                    {
                        "pluginId": plugin_id,
                        "version": "0.2.0",
                        "installed": True,
                        "enabled": True,
                        "source": {"path": "missing-stale-cache"},
                    }
                ]
            }
        )
        commands: list[list[str]] = []

        def fake_run_cli(command: list[str]) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            stdout = stale_json if command[-3:] == ["plugin", "list", "--json"] else "{}"
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

        args = installer.argparse.Namespace(
            command="install", platforms=["codex"], force=False
        )
        with (
            mock.patch.object(installer, "parse_args", return_value=args),
            mock.patch.object(installer, "run_cli", side_effect=fake_run_cli),
            mock.patch.object(installer, "target_roots", return_value=()),
            mock.patch.object(
                installer.shutil,
                "which",
                side_effect=lambda name: "C:/bin/codex.cmd" if name == "codex.cmd" else None,
            ),
        ):
            self.assertEqual(installer.main(), 0)

        self.assertEqual(
            commands,
            [
                ["C:/bin/codex.cmd", "plugin", "list", "--json"],
                ["C:/bin/codex.cmd", "plugin", "remove", plugin_id],
                ["C:/bin/codex.cmd", "plugin", "add", plugin_id, "--json"],
            ],
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
