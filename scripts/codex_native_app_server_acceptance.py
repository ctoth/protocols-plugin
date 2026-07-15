#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Live native Codex collaboration acceptance through app-server JSON-RPC."""

from __future__ import annotations

import hashlib
import json
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import install_skills


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "iterations" / "006" / "live"
TIMEOUT_SECONDS = 360.0


def object_value(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise RuntimeError(f"{label} is not a JSON object")
    return value


def string_value(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{label} is not a non-empty string")
    return value


class AppServer:
    def __init__(self) -> None:
        self.process = subprocess.Popen(
            install_skills.codex_cli_cmd(
                "--dangerously-bypass-hook-trust", "app-server", "--stdio"
            ),
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if self.process.stdin is None or self.process.stdout is None or self.process.stderr is None:
            self.process.kill()
            raise RuntimeError("Codex app-server stdio pipes are unavailable")
        self.inbox: queue.Queue[dict[str, object] | None] = queue.Queue()
        self.messages: list[dict[str, object]] = []
        self.stderr_lines: list[str] = []
        self.next_id = 1
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and all(isinstance(key, str) for key in value):
                self.messages.append(value)
                self.inbox.put(value)
        self.inbox.put(None)

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        self.stderr_lines.extend(self.process.stderr)

    def send_notification(self, method: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps({"method": method}) + "\n")
        self.process.stdin.flush()

    def request(self, method: str, params: dict[str, object]) -> object:
        request_id = self.next_id
        self.next_id += 1
        assert self.process.stdin is not None
        self.process.stdin.write(
            json.dumps({"method": method, "id": request_id, "params": params}) + "\n"
        )
        self.process.stdin.flush()
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while True:
            message = self.read(deadline)
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(f"Codex app-server {method} failed: {message['error']}")
            return message.get("result")

    def read(self, deadline: float) -> dict[str, object]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("Codex app-server acceptance timed out")
        try:
            message = self.inbox.get(timeout=remaining)
        except queue.Empty as error:
            raise RuntimeError("Codex app-server acceptance timed out") from error
        if message is None:
            raise RuntimeError("Codex app-server closed before acceptance completed")
        return message

    def close(self) -> None:
        if self.process.stdin is not None and not self.process.stdin.closed:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=10)

    def write_artifacts(self) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "app-server.jsonl").write_text(
            "".join(json.dumps(message, sort_keys=True) + "\n" for message in self.messages),
            encoding="utf-8",
        )
        (OUT / "stderr.txt").write_text("".join(self.stderr_lines), encoding="utf-8")


def item_notification(message: dict[str, object]) -> tuple[str, dict[str, object]] | None:
    if message.get("method") != "item/completed":
        return None
    params = object_value(message.get("params"), "item/completed params")
    thread_id = string_value(params.get("threadId"), "item/completed threadId")
    item = object_value(params.get("item"), "item/completed item")
    return thread_id, item


def ward_actor_path(root_thread_id: str, child_thread_id: str) -> Path:
    family_hash = hashlib.sha256(root_thread_id.encode()).hexdigest()
    actor_hash = hashlib.sha256(child_thread_id.encode()).hexdigest()
    return Path(tempfile.gettempdir()) / "ward" / "families" / family_hash / "actors" / f"{actor_hash}.json"


def prove_ward_write_denial(
    root_thread_id: str, child_thread_id: str, forbidden: Path
) -> dict[str, object]:
    ward = shutil.which("ward.exe") or shutil.which("ward")
    if ward is None:
        raise RuntimeError("Ward executable is unavailable")
    event = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {
            "command": f"Set-Content -Path '{forbidden}' -Value forbidden"
        },
        "session_id": root_thread_id,
        "agent_id": child_thread_id,
        "cwd": str(ROOT),
    }
    result = subprocess.run(
        [ward, "eval"],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Ward denial probe failed: {result.stderr.strip()}")
    response = object_value(json.loads(result.stdout), "Ward denial response")
    hook_output = object_value(
        response.get("hookSpecificOutput"), "Ward denial hookSpecificOutput"
    )
    reason = hook_output.get("permissionDecisionReason")
    if hook_output.get("permissionDecision") != "deny" or not isinstance(reason, str):
        raise RuntimeError(f"Ward did not deny the harmless write: {response}")
    if "Researcher protocol active" not in reason:
        raise RuntimeError(f"Ward returned the wrong denial reason: {reason}")
    return response


def main() -> None:
    version = subprocess.run(
        install_skills.codex_cli_cmd("--version"),
        text=True,
        capture_output=True,
        check=False,
    )
    if version.returncode != 0 or version.stdout.strip() != "codex-cli 0.144.1":
        raise RuntimeError(f"Expected codex-cli 0.144.1; found {version.stdout.strip()!r}")

    if OUT.exists():
        resolved = OUT.resolve()
        expected_parent = (ROOT / "reports" / "iterations" / "006").resolve()
        if resolved.parent != expected_parent:
            raise RuntimeError(f"Unsafe acceptance output path: {resolved}")
        shutil.rmtree(resolved)
    OUT.mkdir(parents=True)

    fixture = Path(tempfile.mkdtemp(prefix="protocols-codex-native-app-server-"))
    forbidden = fixture / "forbidden.txt"
    release = fixture / "release.txt"
    (fixture / "hold.txt").write_text("hold\n", encoding="utf-8")
    server = AppServer()
    root_thread_id = ""
    child_thread_id = ""
    actor_path: Path | None = None
    actor_snapshot: dict[str, object] | None = None
    delegation_accepted = False
    allowed_rg = False
    denied_write = False
    ward_denial = False
    native_start_hook = False

    try:
        server.request(
            "initialize",
            {
                "clientInfo": {
                    "name": "protocols_native_acceptance",
                    "title": "Protocols Native Acceptance",
                    "version": install_skills.REQUIRED_PROTOCOLS_VERSION,
                }
            },
        )
        server.send_notification("initialized")
        thread_result = object_value(
            server.request(
                "thread/start",
                {
                    "cwd": str(ROOT),
                    "approvalPolicy": "never",
                    "sandbox": "danger-full-access",
                    "ephemeral": True,
                },
            ),
            "thread/start result",
        )
        thread = object_value(thread_result.get("thread"), "thread/start thread")
        root_thread_id = string_value(thread.get("id"), "thread/start thread.id")

        fixture_text = str(fixture)
        prompt = (
            "First run the exact standalone command ward set foreman. Then use native "
            "collaboration spawn exactly once without selecting an agent_type and with "
            "fork_turns set to none. The spawn message's exact first line must be "
            "WARD-DELEGATE/1 phase=researcher, followed by this real task: "
            "do not run ward set; after Ward's injected acceptance command succeeds, run the exact read-only command "
            f"rg --files '{fixture_text}'; then attempt the exact harmless write command "
            f"Set-Content -Path '{forbidden}' -Value forbidden and accept Ward's denial; "
            f"then repeatedly run only rg --files '{fixture_text}' until release.txt appears, "
            "and return both outcomes. Wait for the worker, close that same worker with the "
            "native close tool, and then finish. Do not launch any other worker."
        )
        server.request(
            "turn/start",
            {
                "threadId": root_thread_id,
                "input": [{"type": "text", "text": prompt, "textElements": []}],
            },
        )

        deadline = time.monotonic() + TIMEOUT_SECONDS
        turn_completed = False
        while not turn_completed:
            message = server.read(deadline)
            method = message.get("method")
            if method == "turn/completed":
                params = object_value(message.get("params"), "turn/completed params")
                if params.get("threadId") == root_thread_id:
                    turn_completed = True

            notification = item_notification(message)
            if notification is not None:
                thread_id, item = notification
                item_type = item.get("type")
                if (
                    thread_id == root_thread_id
                    and item_type == "subAgentActivity"
                    and item.get("kind") == "started"
                ):
                    child_thread_id = string_value(
                        item.get("agentThreadId"), "subAgentActivity agentThreadId"
                    )
                    actor_path = ward_actor_path(root_thread_id, child_thread_id)
                if thread_id == child_thread_id and item_type == "commandExecution":
                    command = item.get("command")
                    if isinstance(command, str):
                        if "ward accept-delegation " in command:
                            delegation_accepted = (
                                item.get("status") == "completed"
                                and item.get("exitCode") == 0
                            )
                        if "rg --files" in command and fixture_text in command:
                            allowed_rg = (
                                item.get("status") == "completed"
                                and item.get("exitCode") == 0
                            )

            if message.get("method") == "hook/completed" and child_thread_id:
                params = object_value(message.get("params"), "hook/completed params")
                run = object_value(params.get("run"), "hook/completed run")
                source_path = run.get("sourcePath")
                native_start_hook = native_start_hook or (
                    params.get("threadId") == child_thread_id
                    and run.get("eventName") == "subagentStart"
                    and run.get("status") == "completed"
                    and run.get("source") == "plugin"
                    and isinstance(source_path, str)
                    and "protocols-marketplace" in source_path
                    and install_skills.REQUIRED_PROTOCOLS_VERSION in source_path
                )

            if actor_path is not None and actor_path.is_file():
                candidate = object_value(json.loads(actor_path.read_text(encoding="utf-8")), "Ward actor")
                if (
                    candidate.get("actor_key") == child_thread_id
                    and candidate.get("phase") == "researcher"
                    and candidate.get("delegated_by_actor") == "main"
                    and isinstance(candidate.get("delegation_grant_id"), str)
                    and candidate.get("delegation_grant_id")
                ):
                    actor_snapshot = candidate
                    (OUT / "ward-live-actor.json").write_text(
                        json.dumps(candidate, sort_keys=True) + "\n", encoding="utf-8"
                    )

            if (
                actor_snapshot is not None
                and delegation_accepted
                and allowed_rg
                and native_start_hook
                and not ward_denial
            ):
                denial_response = prove_ward_write_denial(
                    root_thread_id, child_thread_id, forbidden
                )
                (OUT / "ward-denial.json").write_text(
                    json.dumps(denial_response, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                ward_denial = True

            if (
                actor_snapshot is not None
                and delegation_accepted
                and allowed_rg
                and native_start_hook
                and ward_denial
                and not release.exists()
            ):
                release.write_text("release\n", encoding="utf-8")

        if not child_thread_id:
            raise RuntimeError("No completed native spawn with one concrete worker ID")
        if not delegation_accepted:
            raise RuntimeError("No completed Ward delegation acceptance command")
        if not allowed_rg:
            raise RuntimeError("No completed rg execution for the spawned worker")
        if not native_start_hook:
            raise RuntimeError("No completed protocols SubagentStart hook for the spawned worker")
        if not ward_denial:
            raise RuntimeError("No explicit Ward denial against the spawned worker actor")
        if actor_snapshot is None:
            raise RuntimeError("No capability-delegated researcher Ward snapshot for the spawned worker")
        if forbidden.exists():
            raise RuntimeError("The harmless forbidden write escaped Ward enforcement")
        actor_cleanup_deadline = time.monotonic() + 15
        assert actor_path is not None
        while actor_path.exists() and time.monotonic() < actor_cleanup_deadline:
            time.sleep(0.1)
        if actor_path.exists():
            raise RuntimeError(f"Exact worker actor state was not removed: {actor_path}")

        server.request("thread/archive", {"threadId": root_thread_id})
        family_path = actor_path.parent.parent
        server.close()
        stderr = "".join(server.stderr_lines)
        denied_write = (
            str(forbidden) in stderr
            and "Command blocked by PreToolUse hook" in stderr
            and "Researcher protocol active" in stderr
        )
        if not denied_write:
            raise RuntimeError("Codex did not record the worker's exact Ward-blocked write")
        family_cleanup_deadline = time.monotonic() + 15
        while family_path.exists() and time.monotonic() < family_cleanup_deadline:
            time.sleep(0.1)
        if family_path.exists():
            raise RuntimeError(f"Exact root session family was not removed: {family_path}")

        metadata = {
            "codex_version": version.stdout.strip(),
            "protocols_version": install_skills.REQUIRED_PROTOCOLS_VERSION,
            "root_thread_id": root_thread_id,
            "child_thread_id": child_thread_id,
            "delegation_accepted": delegation_accepted,
            "allowed_rg": allowed_rg,
            "ward_denial": ward_denial,
            "phase": actor_snapshot["phase"],
            "actor_cleanup": True,
            "session_cleanup": True,
        }
        (OUT / "metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print("REAL NATIVE CODEX APP-SERVER ACCEPTANCE PASSED")
        print(f"root thread id: {root_thread_id}")
        print(f"worker thread id: {child_thread_id}")
        print("delegation acceptance: observed")
        print("allowed rg execution: observed")
        print("explicit Ward write denial: observed")
        print("phase=researcher")
        print("exact actor cleanup: observed")
        print("exact session cleanup: observed")
    finally:
        if server.process.poll() is None:
            server.close()
        server.write_artifacts()
        shutil.rmtree(fixture, ignore_errors=True)


if __name__ == "__main__":
    main()
