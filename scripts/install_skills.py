#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""Install, uninstall, or inspect protocol skills/plugins for Codex, Claude, and Gemini.

Usage:
  uv run scripts/install_skills.py install
  uv run scripts/install_skills.py uninstall
  uv run scripts/install_skills.py doctor

By default, install/uninstall targets Codex, Claude, and Gemini user skill dirs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path


MARKER_FILENAME = ".protocols-plugin-install.json"
DEFAULT_PLATFORMS = ("codex", "claude", "gemini")
REQUIRED_WARD_REVISION = "33f30ec060e20653d6189eca717be4d2bb55ac55"
REQUIRED_PROTOCOLS_VERSION = "0.3.5"
CODEX_PROTOCOLS_PLUGIN_ID = "protocols@protocols-marketplace"
CODEX_SESSION_HOOK_KEY = (
    f"{CODEX_PROTOCOLS_PLUGIN_ID}:hooks/hooks.json:session_start:0:0"
)
CODEX_SUBAGENT_HOOK_KEY = (
    f"{CODEX_PROTOCOLS_PLUGIN_ID}:hooks/hooks.json:subagent_start:0:0"
)
REQUIRED_WARD_HOOKS = {
    "PreToolUse": "eval",
    "SubagentStart": "start-actor",
    "SubagentStop": "end-actor",
    "SessionEnd": "end-session",
}
REQUIRED_CODEX_WARD_HOOKS = {
    "PreToolUse": "eval",
    "SubagentStart": "start-actor",
    "SubagentStop": "end-actor",
}
TOOLING_REQUIREMENTS = {
    "uv": {
        "required": True,
        "reason": "installer/runtime entrypoint",
        "skills": ["all"],
    },
    "ward": {
        "required": True,
        "reason": "actor-scoped mechanical enforcement for restricted protocols",
        "skills": ["foreman", "campaign", "experiment", "adversary", "researcher"],
    },
    "jq": {
        "required": True,
        "reason": "safe Claude SubagentStart role parsing",
        "skills": ["foreman", "campaign", "experiment", "adversary", "researcher"],
    },
}


@dataclass(frozen=True)
class Skill:
    name: str
    path: Path


@dataclass(frozen=True)
class ClaudePlugin:
    name: str


@dataclass(frozen=True)
class ClaudeMarketplace:
    name: str
    path: Path
    plugins: tuple[ClaudePlugin, ...]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def discover_skills(root: Path) -> list[Skill]:
    plugins_root = root / "plugins"
    skills: list[Skill] = []
    seen: dict[str, Path] = {}

    for skill_md in sorted(plugins_root.glob("*/skills/*/SKILL.md")):
        skill_dir = skill_md.parent
        name = skill_dir.name
        if name in seen and seen[name] != skill_dir:
            raise RuntimeError(
                f"Duplicate skill name '{name}' at {skill_dir} and {seen[name]}"
            )
        seen[name] = skill_dir
        skills.append(Skill(name=name, path=skill_dir))

    if not skills:
        raise RuntimeError(f"No skills discovered under {plugins_root}")

    return skills


def discover_claude_marketplace(root: Path) -> ClaudeMarketplace:
    manifest_path = root / ".claude-plugin" / "marketplace.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Missing Claude marketplace manifest: {manifest_path}")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = data.get("name")
    plugins = data.get("plugins")
    if not isinstance(name, str) or not name:
        raise RuntimeError(f"Invalid marketplace name in {manifest_path}")
    if not isinstance(plugins, list) or not plugins:
        raise RuntimeError(f"No plugins listed in {manifest_path}")

    discovered: list[ClaudePlugin] = []
    seen: set[str] = set()
    for plugin in plugins:
        plugin_name = plugin.get("name") if isinstance(plugin, dict) else None
        if not isinstance(plugin_name, str) or not plugin_name:
            raise RuntimeError(f"Invalid plugin entry in {manifest_path}: {plugin!r}")
        if plugin_name in seen:
            raise RuntimeError(f"Duplicate Claude plugin name '{plugin_name}' in {manifest_path}")
        seen.add(plugin_name)
        discovered.append(ClaudePlugin(name=plugin_name))

    return ClaudeMarketplace(name=name, path=manifest_path, plugins=tuple(discovered))


def target_roots(platform_name: str) -> tuple[Path, ...]:
    home = Path.home()
    if platform_name == "codex":
        return (
            home / ".agents" / "skills",
            home / ".codex" / "skills" / "protocols-plugin",
        )
    if platform_name == "claude":
        return (home / ".claude" / "skills",)
    if platform_name == "gemini":
        return (home / ".gemini" / "skills",)
    raise ValueError(f"Unknown platform: {platform_name}")


def run_cli(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        check=False,
    )


def claude_cli_cmd(*args: str) -> list[str]:
    for candidate in ("claude", "claude.cmd", "claude.exe"):
        path = shutil.which(candidate)
        if path:
            return [path, *args]

    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if pwsh is None:
        raise RuntimeError("Claude CLI not found on PATH")

    probe = run_cli([pwsh, "-NoProfile", "-Command", "(Get-Command claude).Source"])
    ensure_success(probe, "resolve claude executable")
    source = probe.stdout.strip()
    if not source:
        raise RuntimeError("Claude CLI not found on PATH")

    if source.lower().endswith(".ps1"):
        return [pwsh, "-NoProfile", "-File", source, *args]

    return [source, *args]


def codex_cli_cmd(*args: str) -> list[str]:
    candidates = ("codex.exe", "codex.cmd") if os.name == "nt" else ("codex",)
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return [path, *args]
    raise RuntimeError("Codex CLI not found on PATH")


def format_cli_output(result: subprocess.CompletedProcess[str]) -> str:
    parts = [result.stdout.strip(), result.stderr.strip()]
    return "\n".join(part for part in parts if part).strip()


def ensure_success(
    result: subprocess.CompletedProcess[str],
    context: str,
    *,
    accept_patterns: tuple[str, ...] = (),
) -> str:
    combined = format_cli_output(result)
    lowered = combined.lower()
    if result.returncode == 0:
        return combined
    if any(pattern in lowered for pattern in accept_patterns):
        return combined
    raise RuntimeError(f"{context} failed:\n{combined or f'exit code {result.returncode}'}")


def parse_claude_plugin_list(output: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        match = re.match(r"^\s*>\s+(.+)$", line)
        if match:
            if current:
                entries.append(current)
            current = {"plugin": match.group(1).strip()}
            continue
        if current is None:
            continue
        field_match = re.match(r"^\s+([A-Za-z]+):\s+(.*)$", line)
        if field_match:
            current[field_match.group(1).lower()] = field_match.group(2).strip()

    if current:
        entries.append(current)

    return entries


def list_claude_plugins() -> list[dict[str, str]]:
    result = run_cli(claude_cli_cmd("plugin", "list"))
    ensure_success(result, "claude plugin list")
    return parse_claude_plugin_list(result.stdout)


def parse_codex_plugin_list(output: str) -> list[dict[str, object]]:
    try:
        data = json.loads(output)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"codex plugin list returned invalid JSON: {error}") from error

    installed = data.get("installed") if isinstance(data, dict) else None
    if not isinstance(installed, list):
        raise RuntimeError("codex plugin list JSON is missing the installed array")
    if not all(isinstance(entry, dict) for entry in installed):
        raise RuntimeError("codex plugin list JSON contains an invalid installed entry")
    return installed


def list_codex_plugins() -> list[dict[str, object]]:
    result = run_cli(codex_cli_cmd("plugin", "list", "--json"))
    ensure_success(result, "codex plugin list --json")
    return parse_codex_plugin_list(result.stdout)


def codex_app_server_call(method: str, params: dict[str, object]) -> object:
    process = subprocess.Popen(
        codex_cli_cmd("app-server", "--stdio"),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    if process.stdin is None or process.stdout is None:
        process.kill()
        raise RuntimeError("Codex app-server stdio pipes are unavailable")

    timed_out = False

    def kill_on_timeout() -> None:
        nonlocal timed_out
        timed_out = True
        process.kill()

    timer = threading.Timer(30, kill_on_timeout)
    timer.start()

    def request(request_id: int, request_method: str, request_params: object) -> object:
        process.stdin.write(
            json.dumps(
                {"method": request_method, "id": request_id, "params": request_params}
            )
            + "\n"
        )
        process.stdin.flush()
        while line := process.stdout.readline():
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(response, dict) or response.get("id") != request_id:
                continue
            if "error" in response:
                raise RuntimeError(
                    f"Codex app-server {request_method} failed: {response['error']}"
                )
            return response.get("result")
        if timed_out:
            raise RuntimeError(f"Codex app-server {request_method} timed out")
        raise RuntimeError(f"Codex app-server {request_method} closed without a response")

    try:
        request(
            1,
            "initialize",
            {
                "clientInfo": {
                    "name": "protocols_plugin_installer",
                    "title": "Protocols Plugin Installer",
                    "version": REQUIRED_PROTOCOLS_VERSION,
                }
            },
        )
        process.stdin.write(json.dumps({"method": "initialized"}) + "\n")
        process.stdin.flush()
        return request(2, method, params)
    finally:
        timer.cancel()
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()


def list_codex_hooks() -> list[dict[str, object]]:
    result = codex_app_server_call("hooks/list", {"cwds": [str(repo_root())]})
    data = result.get("data") if isinstance(result, dict) else None
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise RuntimeError("Codex hooks/list returned invalid data")
    return data


def write_codex_hook_trust(hashes: dict[str, str]) -> None:
    expected_keys = {CODEX_SESSION_HOOK_KEY, CODEX_SUBAGENT_HOOK_KEY}
    if set(hashes) != expected_keys or not all(
        value.startswith("sha256:") for value in hashes.values()
    ):
        raise RuntimeError("Refusing to authorize anything except the two active protocols hooks")
    codex_app_server_call(
        "config/batchWrite",
        {
            "edits": [
                {
                    "keyPath": "hooks.state",
                    "value": {
                        key: {"enabled": True, "trusted_hash": hashes[key]}
                        for key in (CODEX_SESSION_HOOK_KEY, CODEX_SUBAGENT_HOOK_KEY)
                    },
                    "mergeStrategy": "upsert",
                }
            ],
            "reloadUserConfig": True,
        },
    )


def active_codex_plugin_root(entry: dict[str, object]) -> Path | None:
    values = (entry.get("marketplaceName"), entry.get("name"), entry.get("version"))
    cache_root = (
        Path.home() / ".codex" / "plugins" / "cache" / values[0] / values[1] / values[2]
        if all(isinstance(value, str) for value in values)
        else None
    )
    source = entry.get("source")
    source_path = source.get("path") if isinstance(source, dict) else None
    if cache_root is not None and cache_root.is_dir():
        return cache_root
    return Path(source_path) if isinstance(source_path, str) else None


def check_codex_plugin_integrity(
    entries: list[dict[str, object]], source_manifest: Path
) -> list[str]:
    entry = next(
        (
            candidate
            for candidate in entries
            if candidate.get("pluginId") == CODEX_PROTOCOLS_PLUGIN_ID
            and candidate.get("installed") is True
        ),
        None,
    )
    plugin_root = active_codex_plugin_root(entry) if entry else None
    if plugin_root is None:
        return ["Codex protocols plugin cache root is unavailable"]
    source_hooks = source_manifest.parent
    failures: list[str] = []
    for name in ("hooks.json", "ward-register.sh", "ward-role.sh"):
        source_path = source_hooks / name
        cached_path = plugin_root / "hooks" / name
        try:
            matches = source_path.read_bytes() == cached_path.read_bytes()
        except OSError as error:
            failures.append(f"Codex hook cache integrity unreadable for {name}: {error}")
            continue
        if not matches:
            failures.append(f"Codex hook cache differs from source: {name}")
    return failures


def check_codex_plugin_compatibility(
    entries: list[dict[str, object]], hook_results: list[dict[str, object]]
) -> list[str]:
    entry = next(
        (
            candidate
            for candidate in entries
            if candidate.get("pluginId") == CODEX_PROTOCOLS_PLUGIN_ID
            and candidate.get("installed") is True
        ),
        None,
    )
    if entry is None:
        return [f"Codex plugin {CODEX_PROTOCOLS_PLUGIN_ID} is not installed"]

    failures: list[str] = []
    if entry.get("enabled") is not True:
        failures.append(f"Codex plugin {CODEX_PROTOCOLS_PLUGIN_ID} is not enabled")
    if entry.get("version") != REQUIRED_PROTOCOLS_VERSION:
        failures.append(
            f"Codex plugin {CODEX_PROTOCOLS_PLUGIN_ID} is "
            f"{entry.get('version', 'unknown')}; required {REQUIRED_PROTOCOLS_VERSION}"
        )

    plugin_root = active_codex_plugin_root(entry)
    expected_source = plugin_root / "hooks" / "hooks.json" if plugin_root else None
    for result in hook_results:
        warnings = result.get("warnings")
        errors = result.get("errors")
        if isinstance(warnings, list) and warnings:
            failures.append(f"Codex hooks/list load warning: {warnings}")
        if isinstance(errors, list) and errors:
            failures.append(f"Codex hooks/list load error: {errors}")
    handlers = [
        hook
        for result in hook_results
        for hook in (result.get("hooks") if isinstance(result.get("hooks"), list) else [])
        if isinstance(hook, dict) and hook.get("key") == CODEX_SUBAGENT_HOOK_KEY
    ]
    if not handlers:
        failures.append(f"Codex live hook is missing: {CODEX_SUBAGENT_HOOK_KEY}")
        return failures
    hook = handlers[0]
    expected = {
        "eventName": "subagentStart",
        "handlerType": "command",
        "source": "plugin",
        "pluginId": CODEX_PROTOCOLS_PLUGIN_ID,
    }
    for field, value in expected.items():
        if hook.get(field) != value:
            failures.append(f"Codex live hook has wrong {field}: {hook.get(field)!r}")
    command = hook.get("command")
    if not isinstance(command, str) or not all(
        token in command.replace("\\", "/")
        for token in ("sh.exe -lc", "cygpath -u", "/hooks/ward-role.sh")
    ) or "bash.exe" in command:
        failures.append("Codex live hook has wrong Windows command for ward-role.sh")
    source_path = hook.get("sourcePath")
    if expected_source is None or not isinstance(source_path, str) or (
        os.path.normcase(os.path.abspath(source_path))
        != os.path.normcase(os.path.abspath(expected_source))
    ):
        failures.append("Codex live hook is not from the active cache manifest")
    if hook.get("enabled") is not True:
        failures.append(f"Codex live hook is disabled: {CODEX_SUBAGENT_HOOK_KEY}")
    trust_status = hook.get("trustStatus")
    if trust_status != "trusted":
        failures.append(
            f"Codex live hook {CODEX_SUBAGENT_HOOK_KEY} is {trust_status}; "
            "rerun install with --trust-codex-hooks"
        )
    return failures


def codex_hook_hashes_for_authorization(
    entries: list[dict[str, object]], hook_results: list[dict[str, object]]
) -> dict[str, str]:
    entry = next(
        (
            candidate
            for candidate in entries
            if candidate.get("pluginId") == CODEX_PROTOCOLS_PLUGIN_ID
            and candidate.get("installed") is True
        ),
        None,
    )
    plugin_root = active_codex_plugin_root(entry) if entry else None
    expected_source = plugin_root / "hooks" / "hooks.json" if plugin_root else None
    expected = {
        CODEX_SESSION_HOOK_KEY: ("sessionStart", "/hooks/ward-register.sh"),
        CODEX_SUBAGENT_HOOK_KEY: ("subagentStart", "/hooks/ward-role.sh"),
    }
    for result in hook_results:
        if result.get("warnings") or result.get("errors"):
            raise RuntimeError(
                f"Codex hooks/list reported load failures: "
                f"warnings={result.get('warnings')!r}, errors={result.get('errors')!r}"
            )
    all_hooks = [
        hook
        for result in hook_results
        for hook in (result.get("hooks") if isinstance(result.get("hooks"), list) else [])
        if isinstance(hook, dict)
    ]
    hashes: dict[str, str] = {}
    for key, (event_name, script_suffix) in expected.items():
        hook = next((candidate for candidate in all_hooks if candidate.get("key") == key), None)
        if hook is None:
            raise RuntimeError(f"Codex hooks/list is missing active protocols hook {key}")
        command = hook.get("command")
        source_path = hook.get("sourcePath")
        current_hash = hook.get("currentHash")
        if (
            hook.get("eventName") != event_name
            or hook.get("handlerType") != "command"
            or hook.get("source") != "plugin"
            or hook.get("pluginId") != CODEX_PROTOCOLS_PLUGIN_ID
            or not isinstance(command, str)
            or "sh.exe -lc" not in command
            or "cygpath -u" not in command
            or script_suffix not in command.replace("\\", "/")
            or "bash.exe" in command
            or expected_source is None
            or not isinstance(source_path, str)
            or os.path.normcase(os.path.abspath(source_path))
            != os.path.normcase(os.path.abspath(expected_source))
            or not isinstance(current_hash, str)
            or not current_hash.startswith("sha256:")
        ):
            raise RuntimeError(f"Codex hook is not the exact active protocols handler: {key}")
        hashes[key] = current_hash
    return hashes


def install_codex_plugin(force: bool, *, trust_hooks: bool) -> str:
    entries = list_codex_plugins()
    installed = any(
        entry.get("pluginId") == CODEX_PROTOCOLS_PLUGIN_ID
        and entry.get("installed") is True
        for entry in entries
    )
    source_manifest = repo_root() / "plugins" / "protocols" / "hooks" / "hooks.json"
    entry = next(
        (
            candidate
            for candidate in entries
            if candidate.get("pluginId") == CODEX_PROTOCOLS_PLUGIN_ID
            and candidate.get("installed") is True
        ),
        None,
    )
    stale = bool(
        entry is not None
        and (
            entry.get("enabled") is not True
            or entry.get("version") != REQUIRED_PROTOCOLS_VERSION
            or check_codex_plugin_integrity(entries, source_manifest)
        )
    )
    if installed and (stale or force):
        remove_result = run_cli(
            codex_cli_cmd("plugin", "remove", CODEX_PROTOCOLS_PLUGIN_ID)
        )
        ensure_success(remove_result, f"codex plugin remove {CODEX_PROTOCOLS_PLUGIN_ID}")
    if not installed or stale or force:
        add_result = run_cli(
            codex_cli_cmd("plugin", "add", CODEX_PROTOCOLS_PLUGIN_ID, "--json")
        )
        ensure_success(add_result, f"codex plugin add {CODEX_PROTOCOLS_PLUGIN_ID}")
        install_status = "refreshed" if installed else "installed"
    else:
        install_status = "unchanged"

    hook_results = list_codex_hooks()
    current_entries = list_codex_plugins() if install_status != "unchanged" else entries
    hashes = codex_hook_hashes_for_authorization(current_entries, hook_results)
    trusted = all(
        any(
            hook.get("key") == key
            and hook.get("enabled") is True
            and hook.get("trustStatus") == "trusted"
            for result in hook_results
            for hook in (result.get("hooks") if isinstance(result.get("hooks"), list) else [])
            if isinstance(hook, dict)
        )
        for key in hashes
    )
    if trusted:
        return install_status
    if not trust_hooks:
        raise RuntimeError(
            "Codex protocols hooks are not authorized. Rerun with "
            "--trust-codex-hooks to trust exactly the active SessionStart and "
            "SubagentStart hashes."
        )
    write_codex_hook_trust(hashes)
    verified = list_codex_hooks()
    verified_hashes = codex_hook_hashes_for_authorization(current_entries, verified)
    failures = check_codex_plugin_compatibility(current_entries, verified)
    for key in verified_hashes:
        if not any(
            hook.get("key") == key
            and hook.get("enabled") is True
            and hook.get("trustStatus") == "trusted"
            for result in verified
            for hook in (result.get("hooks") if isinstance(result.get("hooks"), list) else [])
            if isinstance(hook, dict)
        ):
            failures.append(f"Codex hook authorization is absent after write: {key}")
    if failures:
        raise RuntimeError(
            "Codex hook authorization did not become active: " + "; ".join(failures)
        )
    return "authorized" if install_status == "unchanged" else f"{install_status}, authorized"


def uninstall_codex_plugin() -> str:
    entries = list_codex_plugins()
    installed = any(
        entry.get("pluginId") == CODEX_PROTOCOLS_PLUGIN_ID
        and entry.get("installed") is True
        for entry in entries
    )
    if not installed:
        return "missing"
    result = run_cli(codex_cli_cmd("plugin", "remove", CODEX_PROTOCOLS_PLUGIN_ID))
    ensure_success(result, f"codex plugin remove {CODEX_PROTOCOLS_PLUGIN_ID}")
    return "removed"


def installed_hook_commands(settings_path: Path) -> dict[str, list[str]]:
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    commands: dict[str, list[str]] = {}
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        return commands
    for event_name, groups in hooks.items():
        if not isinstance(event_name, str) or not isinstance(groups, list):
            continue
        event_commands: list[str] = []
        for group in groups:
            nested = group.get("hooks", []) if isinstance(group, dict) else []
            if not isinstance(nested, list):
                continue
            for hook in nested:
                command = hook.get("command") if isinstance(hook, dict) else None
                if isinstance(command, str):
                    args = hook.get("args")
                    if isinstance(args, list) and all(
                        isinstance(arg, str) for arg in args
                    ):
                        command = " ".join((command, *args))
                    event_commands.append(command)
        commands[event_name] = event_commands
    return commands


def check_codex_ward_hooks(commands: dict[str, list[str]]) -> list[str]:
    failures: list[str] = []
    for event_name, subcommand in REQUIRED_CODEX_WARD_HOOKS.items():
        if not any(
            re.search(
                rf"(?:^|[/\\])ward(?:\.exe)?[\"']?\s+{re.escape(subcommand)}(?:\s|$)",
                command,
            )
            for command in commands.get(event_name, [])
        ):
            failures.append(
                f"Missing Ward {event_name} hook for `{subcommand}` in ~/.codex/hooks.json; "
                "run `ward install`"
            )
    return failures


def check_codex_windows_tools() -> list[str]:
    if os.name != "nt":
        return []
    failures: list[str] = []
    sh_path = shutil.which("sh.exe")
    cygpath_path = shutil.which("cygpath.exe")
    if sh_path is None:
        failures.append(
            "Codex Windows hooks require sh.exe from a POSIX shell distribution"
        )
    if cygpath_path is None:
        failures.append(
            "Codex Windows hooks require cygpath from the same POSIX shell distribution"
        )
    elif sh_path is not None:
        probe = run_cli([sh_path, "-lc", "command -v cygpath"])
        if probe.returncode != 0 or not probe.stdout.strip():
            failures.append(
                "Codex Windows hooks require cygpath to be available inside sh.exe"
            )
    return failures


def check_ward_compatibility(ward_path: str) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    details: list[str] = []

    for args, required_text in (
        (("start-actor", "--help"), "uninitialized phase"),
        (("set", "--help"), "--hook-input"),
        (("end-actor", "--help"), "Delete one actor"),
        (("end-session", "--help"), "session family"),
        (("accept-delegation", "--help"), "parent-issued child capability"),
    ):
        result = run_cli([ward_path, *args])
        output = format_cli_output(result)
        if result.returncode != 0 or required_text.lower() not in output.lower():
            failures.append(f"Ward lacks required capability: {' '.join(args)}")

    go_path = shutil.which("go")
    if go_path is None:
        failures.append("Go is required to verify the installed Ward build revision")
    else:
        result = run_cli([go_path, "version", "-m", ward_path])
        output = format_cli_output(result)
        revision_match = re.search(r"build\s+vcs\.revision=([0-9a-f]{40})", output)
        modified_match = re.search(r"build\s+vcs\.modified=(\w+)", output)
        revision = revision_match.group(1) if revision_match else "unknown"
        details.append(f"Ward revision: {revision}")
        if revision != REQUIRED_WARD_REVISION:
            failures.append(
                f"Ward revision {revision} is incompatible; required {REQUIRED_WARD_REVISION}"
            )
        if modified_match is None or modified_match.group(1) != "false":
            failures.append("Ward binary must be built from a clean committed tree")

    profiles = run_cli([ward_path, "list-profiles"])
    profile_output = format_cli_output(profiles)
    expected_profile = f"protocols-gates\t{REQUIRED_PROTOCOLS_VERSION}"
    if profiles.returncode != 0 or expected_profile not in profile_output:
        failures.append(
            "Installed protocols-gates profile is missing or incompatible; "
            f"required {REQUIRED_PROTOCOLS_VERSION}"
        )

    installed_hooks = installed_hook_commands(Path.home() / ".claude" / "settings.json")
    for event_name, subcommand in REQUIRED_WARD_HOOKS.items():
        event_commands = installed_hooks.get(event_name, [])
        if not any(
            re.search(rf"(?:^|[/\\])ward(?:\.exe)?\s+{re.escape(subcommand)}(?:\s|$)", command)
            for command in event_commands
        ):
            failures.append(
                f"Missing Ward {event_name} hook for `{subcommand}`; run `ward install`"
            )

    return failures, details


def check_claude_plugin_compatibility(
    entries: list[dict[str, str]], marketplace: ClaudeMarketplace
) -> list[str]:
    failures: list[str] = []
    for plugin in marketplace.plugins:
        plugin_id = f"{plugin.name}@{marketplace.name}"
        entry = next(
            (
                candidate
                for candidate in entries
                if candidate.get("plugin") == plugin_id
                and candidate.get("scope", "").lower() == "user"
            ),
            None,
        )
        if entry is None:
            failures.append(f"Claude plugin {plugin_id} is not installed at user scope")
            continue
        if entry.get("version") != REQUIRED_PROTOCOLS_VERSION:
            failures.append(
                f"Claude plugin {plugin_id} is {entry.get('version', 'unknown')}; "
                f"required {REQUIRED_PROTOCOLS_VERSION}"
            )
        if "enabled" not in entry.get("status", "").lower():
            failures.append(f"Claude plugin {plugin_id} is not enabled")
    return failures


def claude_plugin_installed(
    entries: list[dict[str, str]],
    plugin_name: str,
    marketplace_name: str,
    *,
    scope: str = "user",
) -> bool:
    plugin_id = f"{plugin_name}@{marketplace_name}"
    for entry in entries:
        if entry.get("plugin") != plugin_id:
            continue
        if entry.get("scope", "").lower() == scope:
            return True
    return False


def install_claude_plugins(
    root: Path,
    marketplace: ClaudeMarketplace,
    force: bool,
) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []

    add_result = run_cli(
        claude_cli_cmd(
            "plugin",
            "marketplace",
            "add",
            str(root),
            "--scope",
            "user",
        )
    )
    add_output = ensure_success(
        add_result,
        "claude plugin marketplace add",
        accept_patterns=("already exists", "already added", "already configured"),
    )
    add_status = "added" if add_result.returncode == 0 else "unchanged"
    if add_output:
        add_status = f"{add_status} ({add_output.splitlines()[0]})"
    results.append((f"marketplace:{marketplace.name}", add_status))

    installed = list_claude_plugins()
    for plugin in marketplace.plugins:
        plugin_id = f"{plugin.name}@{marketplace.name}"
        installed_entry = next(
            (
                entry
                for entry in installed
                if entry.get("plugin") == plugin_id
                and entry.get("scope", "").lower() == "user"
            ),
            None,
        )
        is_installed = installed_entry is not None
        is_stale = bool(
            installed_entry is not None
            and installed_entry.get("version") != REQUIRED_PROTOCOLS_VERSION
        )
        if is_installed and not force and not is_stale:
            results.append((plugin.name, "unchanged"))
            continue

        if is_installed and (force or is_stale):
            remove_result = run_cli(
                claude_cli_cmd("plugin", "uninstall", plugin_id, "--scope", "user")
            )
            ensure_success(
                remove_result,
                f"claude plugin uninstall {plugin_id}",
                accept_patterns=("not installed", "not found"),
            )

        install_result = run_cli(
            claude_cli_cmd("plugin", "install", plugin_id, "--scope", "user")
        )
        install_output = ensure_success(
            install_result,
            f"claude plugin install {plugin_id}",
            accept_patterns=("already installed",),
        )
        if install_result.returncode == 0:
            status = "refreshed" if is_installed else "installed"
        else:
            status = "unchanged"
        if install_output:
            status = f"{status} ({install_output.splitlines()[0]})"
        results.append((plugin.name, status))

    return results


def uninstall_claude_plugins(
    marketplace: ClaudeMarketplace,
    force: bool,
) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    installed = list_claude_plugins()

    for plugin in marketplace.plugins:
        plugin_id = f"{plugin.name}@{marketplace.name}"
        if not claude_plugin_installed(installed, plugin.name, marketplace.name):
            results.append((plugin.name, "missing"))
            continue

        remove_result = run_cli(
            claude_cli_cmd("plugin", "uninstall", plugin_id, "--scope", "user")
        )
        remove_output = ensure_success(
            remove_result,
            f"claude plugin uninstall {plugin_id}",
            accept_patterns=("not installed", "not found"),
        )
        status = "removed" if remove_result.returncode == 0 else "missing"
        if remove_output:
            status = f"{status} ({remove_output.splitlines()[0]})"
        results.append((plugin.name, status))

    marketplace_remove = run_cli(
        claude_cli_cmd("plugin", "marketplace", "remove", marketplace.name)
    )
    remove_output = format_cli_output(marketplace_remove)
    if marketplace_remove.returncode == 0:
        status = "removed"
    else:
        lowered = remove_output.lower()
        if any(token in lowered for token in ("not found", "does not exist", "unknown marketplace")):
            status = "missing"
        elif force:
            status = f"skipped ({remove_output.splitlines()[0]})" if remove_output else "skipped"
        else:
            raise RuntimeError(
                "claude plugin marketplace remove failed:\n"
                + (remove_output or f"exit code {marketplace_remove.returncode}")
            )
    results.append((f"marketplace:{marketplace.name}", status))
    return results


def managed_marker(dest: Path) -> Path:
    return dest / MARKER_FILENAME


def marker_payload(source: Path, platform_name: str) -> dict[str, str]:
    return {
        "installed_from": str(source.resolve()),
        "platform": platform_name,
        "installer": str(Path(__file__).resolve()),
    }


def load_marker(dest: Path) -> dict[str, str] | None:
    marker = managed_marker(dest)
    if not marker.is_file():
        return None
    try:
        return json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return None


def remove_existing(dest: Path) -> None:
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.exists():
        shutil.rmtree(dest)


def is_managed_copy(dest: Path, source: Path) -> bool:
    payload = load_marker(dest)
    return payload is not None and payload.get("installed_from") == str(source.resolve())


def is_matching_symlink(dest: Path, source: Path) -> bool:
    if not dest.is_symlink():
        return False
    try:
        return dest.resolve() == source.resolve()
    except OSError:
        return False


def install_skill(skill: Skill, dest_root: Path, platform_name: str, force: bool) -> str:
    dest_root.mkdir(parents=True, exist_ok=True)
    dest = dest_root / skill.name

    if dest.exists() or dest.is_symlink():
        if is_matching_symlink(dest, skill.path) or is_managed_copy(dest, skill.path):
            return "unchanged"
        if not force:
            raise RuntimeError(
                f"Destination exists and is not managed by this installer: {dest}"
            )
        remove_existing(dest)

    try:
        os.symlink(str(skill.path), str(dest), target_is_directory=True)
        return "linked"
    except OSError:
        shutil.copytree(skill.path, dest, symlinks=False)
        managed_marker(dest).write_text(
            json.dumps(marker_payload(skill.path, platform_name), indent=2) + "\n",
            encoding="utf-8",
        )
        return "copied"


def uninstall_skill(skill: Skill, dest_root: Path, force: bool) -> str:
    dest = dest_root / skill.name
    if not dest.exists() and not dest.is_symlink():
        return "missing"

    if is_matching_symlink(dest, skill.path) or is_managed_copy(dest, skill.path):
        remove_existing(dest)
        return "removed"

    if force:
        remove_existing(dest)
        return "removed-force"

    return "skipped"


def run_doctor(skills: list[Skill]) -> int:
    root = repo_root()
    marketplace = discover_claude_marketplace(root)
    print("Skill discovery:")
    for skill in skills:
        print(f"  - {skill.name}: {skill.path}")

    print("\nClaude marketplace:")
    print(f"  - {marketplace.name}: {marketplace.path}")
    for plugin in marketplace.plugins:
        print(f"      plugin: {plugin.name}")

    print("\nTooling:")
    failures = 0
    found_tools: dict[str, str | None] = {}
    for tool, meta in TOOLING_REQUIREMENTS.items():
        if tool == "python":
            found = sys.executable
        else:
            found = shutil.which(tool)
        found_tools[tool] = found
        status = "OK" if found else ("MISSING" if meta["required"] else "WARN")
        skills_text = ", ".join(meta["skills"])
        print(
            f"  - {tool}: {status}"
            f" | {meta['reason']}"
            f" | affects: {skills_text}"
        )
        if found:
            print(f"      {found}")
        elif meta["required"]:
            failures += 1

    print("\nWard and Claude lifecycle compatibility:")
    ward_path = found_tools.get("ward")
    if ward_path:
        ward_failures, ward_details = check_ward_compatibility(ward_path)
        for detail in ward_details:
            print(f"  - {detail}")
        if ward_failures:
            for failure in ward_failures:
                print(f"  - FAIL: {failure}")
            failures += len(ward_failures)
        else:
            print(
                "  - OK: actor scope, Claude lifecycle hooks, build revision, and profile"
            )
    else:
        print("  - FAIL: Ward executable unavailable")

    claude_path = shutil.which("claude")
    status = "OK" if claude_path else "MISSING"
    print("  - claude: " + status + " | native marketplace install path | affects: claude")
    if claude_path:
        print(f"      {claude_path}")
        try:
            claude_failures = check_claude_plugin_compatibility(
                list_claude_plugins(), marketplace
            )
        except RuntimeError as error:
            claude_failures = [str(error)]
        if claude_failures:
            for failure in claude_failures:
                print(f"  - FAIL: {failure}")
            failures += len(claude_failures)
        else:
            print(f"  - OK: Claude plugin version {REQUIRED_PROTOCOLS_VERSION}")
    else:
        failures += 1

    try:
        codex_path = codex_cli_cmd()[0]
    except RuntimeError:
        codex_path = None
    status = "OK" if codex_path else "MISSING"
    print("  - codex: " + status + " | native plugin install path | affects: codex")
    if codex_path:
        print(f"      {codex_path}")
        try:
            codex_entries = list_codex_plugins()
            codex_hooks = list_codex_hooks()
            codex_failures = check_codex_plugin_compatibility(
                codex_entries, codex_hooks
            )
            integrity_failures = check_codex_plugin_integrity(
                codex_entries,
                root / "plugins" / "protocols" / "hooks" / "hooks.json",
            )
            windows_failures = check_codex_windows_tools()
            lifecycle_failures = check_codex_ward_hooks(
                installed_hook_commands(Path.home() / ".codex" / "hooks.json")
            )
        except RuntimeError as error:
            codex_failures = [str(error)]
            integrity_failures = []
            windows_failures = []
            lifecycle_failures = []
        if codex_failures:
            for failure in codex_failures:
                print(f"  - FAIL: {failure}")
            failures += len(codex_failures)
        else:
            print(
                "  - OK: live Codex SubagentStart hook is enabled, trusted, "
                "and active"
            )
        if integrity_failures:
            for failure in integrity_failures:
                print(f"  - FAIL: {failure}")
            failures += len(integrity_failures)
        else:
            print("  - OK: Codex plugin source/cache hook integrity")
        for failure_group in (windows_failures, lifecycle_failures):
            if failure_group:
                for failure in failure_group:
                    print(f"  - FAIL: {failure}")
                failures += len(failure_group)
        if not windows_failures:
            print("  - OK: Codex Windows sh.exe and cygpath prerequisites")
        if not lifecycle_failures:
            print("  - OK: full Codex Ward lifecycle hook chain")
    else:
        failures += 1

    manifest_path = root / "plugins" / "protocols" / ".claude-plugin" / "plugin.json"
    profile_path = root / "plugins" / "protocols" / "ward-profile" / "profile.yaml"
    manifest_version = json.loads(manifest_path.read_text(encoding="utf-8")).get("version")
    profile_match = re.search(
        r"^version:\s*(\S+)", profile_path.read_text(encoding="utf-8"), re.MULTILINE
    )
    profile_version = profile_match.group(1) if profile_match else None
    if manifest_version != REQUIRED_PROTOCOLS_VERSION or profile_version != REQUIRED_PROTOCOLS_VERSION:
        print(
            "  - FAIL: source plugin/profile versions are incoherent "
            f"({manifest_version}, {profile_version}; required {REQUIRED_PROTOCOLS_VERSION})"
        )
        failures += 1

    print("\nTarget roots:")
    for platform_name in DEFAULT_PLATFORMS:
        if platform_name == "claude":
            print("  - claude: native plugin install via `claude plugin marketplace add/install`")
        elif platform_name == "codex":
            roots = ", ".join(str(root) for root in target_roots(platform_name))
            print("  - codex: native plugin install via `codex plugin add` plus " + roots)
        else:
            roots = ", ".join(str(root) for root in target_roots(platform_name))
            print(f"  - {platform_name}: {roots}")

    return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=("install", "uninstall", "doctor"),
        help="Action to run",
    )
    parser.add_argument(
        "--platform",
        dest="platforms",
        choices=DEFAULT_PLATFORMS,
        action="append",
        help="Limit to one or more platforms (default: all)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing conflicting installs",
    )
    parser.add_argument(
        "--trust-codex-hooks",
        action="store_true",
        help=(
            "Explicitly authorize only the active protocols SessionStart and "
            "SubagentStart hook hashes returned by Codex hooks/list"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()
    skills = discover_skills(root)
    marketplace = discover_claude_marketplace(root)
    platforms = tuple(args.platforms or DEFAULT_PLATFORMS)

    if args.command == "doctor":
        return run_doctor(skills)

    for platform_name in platforms:
        if platform_name == "claude":
            print(f"{args.command.title()} claude plugins via native Claude CLI")
            claude_cli_cmd("plugin", "list")
            if args.command == "install":
                claude_results = install_claude_plugins(root, marketplace, args.force)
            else:
                claude_results = uninstall_claude_plugins(marketplace, args.force)
            for name, result in claude_results:
                print(f"  - {name}: {result}")
            continue

        if platform_name == "codex":
            print(f"{args.command.title()} codex plugin via native Codex CLI")
            if args.command == "install":
                codex_result = install_codex_plugin(
                    args.force, trust_hooks=args.trust_codex_hooks
                )
            else:
                codex_result = uninstall_codex_plugin()
            print(f"  - {CODEX_PROTOCOLS_PLUGIN_ID}: {codex_result}")

        for dest_root in target_roots(platform_name):
            print(f"{args.command.title()} {platform_name} skills -> {dest_root}")
            for skill in skills:
                if args.command == "install":
                    result = install_skill(skill, dest_root, platform_name, args.force)
                else:
                    result = uninstall_skill(skill, dest_root, args.force)
                print(f"  - {skill.name}: {result}")

    if args.command == "install":
        print(
            "\nRestart Codex/Claude/Gemini if they are already running; "
            "Codex must restart after a native plugin refresh."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
