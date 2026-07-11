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
        self.assertEqual(manifest["version"], "0.3.2")
        self.assertIn("version: 0.3.2", profile)
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
        for event_name, script_name in (
            ("SessionStart", "ward-register.sh"),
            ("SubagentStart", "ward-role.sh"),
        ):
            handlers = [
                hook
                for group in hooks[event_name]
                for hook in group["hooks"]
            ]
            self.assertEqual(len(handlers), 1)
            windows_command = handlers[0]["commandWindows"]
            self.assertIn("sh.exe -lc", windows_command)
            self.assertIn("cygpath -u", windows_command)
            self.assertIn("$PLUGIN_ROOT", windows_command)
            self.assertIn(f"/hooks/{script_name}", windows_command)
            self.assertNotIn("bash.exe", windows_command)

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
            "cea6f35bdc4dea1180f2bb879dcb3a66f430795d",
        )
        self.assertEqual(installer.REQUIRED_PROTOCOLS_VERSION, "0.3.2")
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
                "version": "0.3.2",
                "scope": "user",
                "status": "enabled",
            }
        ]
        self.assertIn("0.1.2", installer.check_claude_plugin_compatibility(stale, marketplace)[0])
        self.assertEqual(
            installer.check_claude_plugin_compatibility(current, marketplace), []
        )

    def test_codex_live_hook_requires_exact_trusted_active_handler(self) -> None:
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
                            "name": "protocols",
                            "marketplaceName": "protocols-marketplace",
                            "version": "0.3.2",
                            "installed": True,
                            "enabled": True,
                            "source": {"path": str(plugin_root)},
                        }
                    ]
                }
            )
            current = installer.parse_codex_plugin_list(current_json)
            hook_key = installer.CODEX_SUBAGENT_HOOK_KEY
            role_command = (
                "sh.exe -lc 'exec \"$(cygpath -u \"$PLUGIN_ROOT\")"
                "/hooks/ward-role.sh\"'"
            )

            def listing(**handler_overrides: object) -> list[dict[str, object]]:
                handler: dict[str, object] = {
                    "key": hook_key,
                    "eventName": "subagentStart",
                    "handlerType": "command",
                    "command": role_command,
                    "sourcePath": str(manifest_path),
                    "source": "plugin",
                    "pluginId": plugin_id,
                    "enabled": True,
                    "currentHash": "sha256:role",
                    "trustStatus": "trusted",
                }
                handler.update(handler_overrides)
                return [
                    {
                        "cwd": str(ROOT),
                        "hooks": [handler],
                        "warnings": [],
                        "errors": [],
                    }
                ]

            with mock.patch.object(
                installer, "active_codex_plugin_root", return_value=plugin_root
            ):
                self.assertEqual(
                    installer.check_codex_plugin_compatibility(current, listing()), []
                )
                integrity = installer.check_codex_plugin_integrity(
                    current,
                    ROOT / "plugins/protocols/hooks/hooks.json",
                )
            self.assertIn("differs from source", " ".join(integrity))

            variants = (
                (listing(trustStatus="untrusted"), "untrusted"),
                (listing(trustStatus="modified"), "modified"),
                (listing(enabled=False), "disabled"),
                (listing(pluginId="other@marketplace"), "wrong pluginId"),
                (listing(eventName="sessionStart"), "wrong eventName"),
                (
                    listing(sourcePath=str(plugin_root / "other/hooks/hooks.json")),
                    "active cache",
                ),
                ([], "missing"),
                ([{**listing()[0], "warnings": ["load warning"]}], "load warning"),
                ([{**listing()[0], "errors": ["load error"]}], "load error"),
            )
            for hooks_result, message in variants:
                with self.subTest(message=message):
                    with mock.patch.object(
                        installer, "active_codex_plugin_root", return_value=plugin_root
                    ):
                        self.assertIn(
                            message,
                            " ".join(
                                installer.check_codex_plugin_compatibility(
                                    current, hooks_result
                                )
                            ),
                        )

    def test_codex_install_trusts_only_active_protocols_hooks_after_consent(self) -> None:
        installer = load_installer()
        plugin_root = Path.home() / ".codex/plugins/cache/protocols-marketplace/protocols/0.3.2"
        entries = [
            {
                "pluginId": installer.CODEX_PROTOCOLS_PLUGIN_ID,
                "name": "protocols",
                "marketplaceName": "protocols-marketplace",
                "version": "0.3.2",
                "installed": True,
                "enabled": True,
                "source": {"path": str(plugin_root)},
            }
        ]
        hashes = {
            installer.CODEX_SESSION_HOOK_KEY: "sha256:session",
            installer.CODEX_SUBAGENT_HOOK_KEY: "sha256:subagent",
        }
        hooks = [
            {
                "key": key,
                "eventName": event,
                "handlerType": "command",
                "command": (
                    "sh.exe -lc 'exec \"$(cygpath -u \"$PLUGIN_ROOT\")"
                    f"/hooks/ward-{script}.sh\"'"
                ),
                "sourcePath": str(plugin_root / "hooks/hooks.json"),
                "source": "plugin",
                "pluginId": installer.CODEX_PROTOCOLS_PLUGIN_ID,
                "enabled": False,
                "currentHash": current_hash,
                "trustStatus": "modified",
            }
            for key, event, script, current_hash in (
                (
                    installer.CODEX_SESSION_HOOK_KEY,
                    "sessionStart",
                    "register",
                    hashes[installer.CODEX_SESSION_HOOK_KEY],
                ),
                (
                    installer.CODEX_SUBAGENT_HOOK_KEY,
                    "subagentStart",
                    "role",
                    hashes[installer.CODEX_SUBAGENT_HOOK_KEY],
                ),
            )
        ]
        hooks.append(
            {
                "key": "unrelated:user-hook:pre_tool_use:0:0",
                "currentHash": "sha256:unrelated",
                "trustStatus": "untrusted",
            }
        )
        listing = [{"cwd": str(ROOT), "hooks": hooks, "warnings": [], "errors": []}]

        trusted_listing = [
            {
                **listing[0],
                "hooks": [
                    {**hook, "enabled": True, "trustStatus": "trusted"}
                    for hook in listing[0]["hooks"]
                ],
            }
        ]
        with (
            mock.patch.object(installer, "list_codex_plugins", return_value=entries),
            mock.patch.object(installer, "check_codex_plugin_integrity", return_value=[]),
            mock.patch.object(
                installer,
                "list_codex_hooks",
                side_effect=(listing, listing, trusted_listing),
            ),
            mock.patch.object(installer, "write_codex_hook_trust") as write_trust,
        ):
            with self.assertRaisesRegex(RuntimeError, "--trust-codex-hooks"):
                installer.install_codex_plugin(False, trust_hooks=False)
            write_trust.assert_not_called()
            self.assertEqual(
                installer.install_codex_plugin(False, trust_hooks=True),
                "authorized",
            )

        write_trust.assert_called_once_with(hashes)

    def test_codex_trust_batch_write_contains_only_protocols_hashes(self) -> None:
        installer = load_installer()
        hashes = {
            installer.CODEX_SESSION_HOOK_KEY: "sha256:session",
            installer.CODEX_SUBAGENT_HOOK_KEY: "sha256:subagent",
        }
        with mock.patch.object(installer, "codex_app_server_call") as app_server_call:
            installer.write_codex_hook_trust(hashes)

        app_server_call.assert_called_once_with(
            "config/batchWrite",
            {
                "edits": [
                    {
                        "keyPath": "hooks.state",
                        "value": {
                            installer.CODEX_SESSION_HOOK_KEY: {
                                "enabled": True,
                                "trusted_hash": "sha256:session",
                            },
                            installer.CODEX_SUBAGENT_HOOK_KEY: {
                                "enabled": True,
                                "trusted_hash": "sha256:subagent",
                            },
                        },
                        "mergeStrategy": "upsert",
                    }
                ],
                "reloadUserConfig": True,
            },
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
        current_json = json.dumps(
            {
                "installed": [
                    {
                        "pluginId": plugin_id,
                        "name": "protocols",
                        "marketplaceName": "protocols-marketplace",
                        "version": "0.3.2",
                        "installed": True,
                        "enabled": True,
                        "source": {"path": "current-cache"},
                    }
                ]
            }
        )
        list_count = 0

        def fake_run_cli(command: list[str]) -> subprocess.CompletedProcess[str]:
            nonlocal list_count
            commands.append(command)
            if command[-3:] == ["plugin", "list", "--json"]:
                list_count += 1
                stdout = stale_json if list_count == 1 else current_json
            else:
                stdout = "{}"
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

        args = installer.argparse.Namespace(
            command="install",
            platforms=["codex"],
            force=False,
            trust_codex_hooks=True,
        )
        with (
            mock.patch.object(installer, "parse_args", return_value=args),
            mock.patch.object(installer, "run_cli", side_effect=fake_run_cli),
            mock.patch.object(installer, "target_roots", return_value=()),
            mock.patch.object(
                installer,
                "list_codex_hooks",
                return_value=[
                    {
                        "hooks": [
                            {
                                "key": installer.CODEX_SESSION_HOOK_KEY,
                                "enabled": True,
                                "trustStatus": "trusted",
                            },
                            {
                                "key": installer.CODEX_SUBAGENT_HOOK_KEY,
                                "enabled": True,
                                "trustStatus": "trusted",
                            },
                        ],
                        "warnings": [],
                        "errors": [],
                    }
                ],
            ),
            mock.patch.object(
                installer,
                "codex_hook_hashes_for_authorization",
                return_value={
                    installer.CODEX_SESSION_HOOK_KEY: "sha256:session",
                    installer.CODEX_SUBAGENT_HOOK_KEY: "sha256:subagent",
                },
            ),
            mock.patch.object(installer, "write_codex_hook_trust"),
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
                ["C:/bin/codex.cmd", "plugin", "list", "--json"],
            ],
        )

    def test_windows_codex_requires_posix_shell_and_cygpath(self) -> None:
        installer = load_installer()
        with mock.patch.object(
            installer.shutil,
            "which",
            side_effect=lambda name: None if name == "sh.exe" else "C:/bin/cygpath.exe",
        ):
            self.assertIn("sh.exe", " ".join(installer.check_codex_windows_tools()))
        with mock.patch.object(
            installer.shutil,
            "which",
            side_effect=lambda name: "C:/bin/sh.exe" if name == "sh.exe" else None,
        ):
            self.assertIn("cygpath", " ".join(installer.check_codex_windows_tools()))

    def test_codex_ward_lifecycle_requires_all_user_hooks(self) -> None:
        installer = load_installer()
        commands = {
            event: [f"C:/bin/ward.exe {subcommand}"]
            for event, subcommand in installer.REQUIRED_WARD_HOOKS.items()
        }
        self.assertEqual(installer.check_codex_ward_hooks(commands), [])
        for event_name in installer.REQUIRED_WARD_HOOKS:
            with self.subTest(event_name=event_name):
                incomplete = {**commands, event_name: []}
                self.assertIn(
                    event_name,
                    " ".join(installer.check_codex_ward_hooks(incomplete)),
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
        codex_acceptance = (
            ROOT / "scripts/codex_native_worker_acceptance.sh"
        ).read_text(encoding="utf-8")
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
        self.assertIn("codex exec", codex_acceptance)
        self.assertIn("codex-cli 0.144.1", codex_acceptance)
        self.assertIn("fresh", codex_acceptance.lower())
        self.assertIn("agent_type=default", codex_acceptance)
        self.assertIn("phase=codex-scout", codex_acceptance)
        self.assertIn("matching actor id", codex_acceptance.lower())
        self.assertIn("plugin hook run", codex_acceptance.lower())
        self.assertIn("enforcement denial", codex_acceptance.lower())
        self.assertIn("actor cleanup", codex_acceptance.lower())
        self.assertNotIn("ward set", codex_acceptance.lower())


if __name__ == "__main__":
    unittest.main()
