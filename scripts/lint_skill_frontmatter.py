#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Lint SKILL.md YAML frontmatter."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised when CI skips script deps
    yaml = None


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def discover_skill_files(root: Path) -> list[Path]:
    return sorted((root / "plugins").glob("*/skills/*/SKILL.md"))


def extract_frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing opening frontmatter delimiter")

    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("missing closing frontmatter delimiter")

    return text[4:end]


def lint_file(path: Path) -> None:
    frontmatter = extract_frontmatter(path)
    if yaml is not None:
        yaml.safe_load(frontmatter)
        return

    lint_simple_frontmatter(frontmatter)


def lint_simple_frontmatter(frontmatter: str) -> None:
    """Validate the simple YAML shape used by skill frontmatter."""
    lines = frontmatter.splitlines()
    if not lines:
        raise ValueError("empty frontmatter")

    current_key: str | None = None
    seen: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue

        if line.startswith("  - "):
            if current_key is None:
                raise ValueError(f"line {line_number}: list item without key")
            if not line[4:].strip():
                raise ValueError(f"line {line_number}: empty list item")
            continue

        if line.startswith(" "):
            raise ValueError(f"line {line_number}: unsupported indentation")

        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"line {line_number}: missing ':'")
        if not key.strip():
            raise ValueError(f"line {line_number}: empty key")
        if key != key.strip():
            raise ValueError(f"line {line_number}: key has surrounding whitespace")
        if key in seen:
            raise ValueError(f"line {line_number}: duplicate key {key!r}")

        seen.add(key)
        current_key = key
        if value and not value.startswith(" "):
            raise ValueError(f"line {line_number}: missing space after ':'")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional SKILL.md paths to lint. Defaults to all plugin skills.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()
    paths = [Path(p).resolve() for p in args.paths] if args.paths else discover_skill_files(root)

    if not paths:
        print("No SKILL.md files found.")
        return 1

    failures = 0
    for path in paths:
        try:
            lint_file(path)
            print(f"OK {path}")
        except Exception as exc:
            failures += 1
            print(f"BAD {path}: {exc}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
