#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Fail-closed classification of Codex exec JSON lifecycle evidence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AcceptanceClassification:
    root_thread_id: str | None
    child_thread_id: str | None
    spawn_failed: bool
    worker_created: bool
    allowed_command_observed: bool
    denial_observed: bool
    cleanup_unproved: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _parse_jsonl(stdout: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(stdout.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"non-JSON stdout at line {line_number}") from error
        if not isinstance(event, dict):
            raise ValueError(f"non-object JSON stdout at line {line_number}")
        events.append(event)
    return events


def _item(event: dict[str, Any]) -> dict[str, Any] | None:
    item = event.get("item")
    return item if isinstance(item, dict) else None


def classify_acceptance(
    stdout: str,
    stderr: str,
    *,
    family_observed: bool,
    family_removed: bool,
) -> AcceptanceClassification:
    """Classify typed evidence; prose never supplies a positive signal."""

    events = _parse_jsonl(stdout)
    root_ids = [
        event.get("thread_id")
        for event in events
        if event.get("type") == "thread.started"
        and isinstance(event.get("thread_id"), str)
    ]
    root_thread_id = root_ids[0] if len(root_ids) == 1 else None

    successful_spawns: list[dict[str, Any]] = []
    typed_spawn_failed = False
    for event in events:
        item = _item(event)
        if item is None or item.get("type") != "collab_tool_call":
            continue
        if item.get("tool") != "spawn_agent":
            continue
        if item.get("status") == "failed":
            typed_spawn_failed = True
        receivers = item.get("receiver_thread_ids")
        sender = item.get("sender_thread_id")
        if (
            event.get("type") == "item.completed"
            and item.get("status") == "completed"
            and sender == root_thread_id
            and isinstance(receivers, list)
            and len(receivers) == 1
            and isinstance(receivers[0], str)
            and receivers[0]
        ):
            successful_spawns.append(item)

    worker_created = len(successful_spawns) == 1
    child_thread_id = (
        successful_spawns[0]["receiver_thread_ids"][0] if worker_created else None
    )

    completed_commands = [
        item
        for event in events
        if event.get("type") == "item.completed"
        for item in [_item(event)]
        if item is not None
        and item.get("type") == "command_execution"
        and item.get("status") == "completed"
    ]
    allowed_command_observed = worker_created and any(
        isinstance(item.get("command"), str)
        and "rg --files" in item["command"]
        and item.get("exit_code") == 0
        for item in completed_commands
    )

    denied_commands = [
        item
        for event in events
        if event.get("type") == "item.completed"
        for item in [_item(event)]
        if item is not None
        and item.get("type") == "command_execution"
        and item.get("status") in {"failed", "declined"}
    ]
    denial_observed = worker_created and child_thread_id is not None and any(
        isinstance(item.get("command"), str)
        and "Set-Content" in item["command"]
        and child_thread_id in stderr
        and "ward" in stderr.lower()
        for item in denied_commands
    )

    spawn_failed = typed_spawn_failed or "collab spawn failed" in stderr.lower()
    cleanup_unproved = not (family_observed and family_removed)
    return AcceptanceClassification(
        root_thread_id=root_thread_id,
        child_thread_id=child_thread_id,
        spawn_failed=spawn_failed,
        worker_created=worker_created,
        allowed_command_observed=allowed_command_observed,
        denial_observed=denial_observed,
        cleanup_unproved=cleanup_unproved,
    )
