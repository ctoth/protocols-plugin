#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Deterministic regressions for native Codex acceptance evidence."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True


def load_parser():
    path = ROOT / "scripts" / "codex_native_acceptance.py"
    spec = importlib.util.spec_from_file_location("codex_native_acceptance", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CodexNativeAcceptanceParserTest(unittest.TestCase):
    def test_preserved_spawn_failure_ignores_distracting_prose(self) -> None:
        parser = load_parser()
        preserved = (
            ROOT
            / "reports"
            / "codex-native-acceptance-failed-codex-native-1783778050-402.jsonl"
        ).read_text(encoding="utf-8")
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        for line in preserved.splitlines():
            if line.startswith("{"):
                stdout_lines.append(line)
            else:
                stderr_lines.append(line)

        result = parser.classify_acceptance(
            "\n".join(stdout_lines) + "\n",
            "\n".join(stderr_lines) + "\n",
            family_observed=False,
            family_removed=False,
        )

        self.assertEqual(
            result.as_dict(),
            {
                "root_thread_id": "019f5175-1493-7cc1-b5e0-2050369255c4",
                "child_thread_id": None,
                "spawn_failed": True,
                "worker_created": False,
                "allowed_command_observed": False,
                "denial_observed": False,
                "cleanup_unproved": True,
            },
        )

    def test_non_json_stdout_is_rejected(self) -> None:
        parser = load_parser()
        with self.assertRaisesRegex(ValueError, "non-JSON stdout"):
            parser.classify_acceptance(
                'diagnostic on stdout\n{"type":"thread.started","thread_id":"root"}\n',
                "",
                family_observed=False,
                family_removed=False,
            )

    def test_persistent_ab_arm_does_not_infer_spawn_from_ward_actor(self) -> None:
        parser = load_parser()
        arm = ROOT / "reports" / "iterations" / "005" / "ephemeral-ab" / "persistent"
        result = parser.classify_acceptance(
            (arm / "stdout.jsonl").read_text(encoding="utf-8"),
            (arm / "stderr.txt").read_text(encoding="utf-8"),
            family_observed=True,
            family_removed=False,
        )

        self.assertEqual(result.root_thread_id, "019f518a-c1c4-78e3-a35a-b2ebf8996155")
        self.assertIsNone(result.child_thread_id)
        self.assertFalse(result.spawn_failed)
        self.assertFalse(result.worker_created)
        self.assertFalse(result.allowed_command_observed)
        self.assertFalse(result.denial_observed)
        self.assertTrue(result.cleanup_unproved)


if __name__ == "__main__":
    unittest.main()
