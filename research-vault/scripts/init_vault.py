#!/usr/bin/env python3
"""Atomically initialize an Obsidian research vault from bundled assets."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


ASSET_FILES = (
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "sources.base",
    "wiki.base",
    "queue.json",
    "shortlist.json",
    "source-note.md",
    "wiki-entry.md",
)

REQUIRED_DIRECTORIES = (
    "raw",
    "markdown",
    "sources",
    "wiki",
    "state",
    "templates",
    "scripts",
)

REQUIRED_FILES = (
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "PARSING.md",
    "sources.base",
    "wiki.base",
    "state/research.md",
    "state/candidates.json",
    "state/acquisition.json",
    "state/parsing.json",
    "state/shortlist.json",
    "state/queue.json",
    "state/search-log.jsonl",
    "templates/source-note.md",
    "templates/wiki-entry.md",
    "scripts/seed_openalex.py",
    "scripts/acquire_openalex.py",
    "scripts/configure_openalex.py",
    "scripts/process_sources.py",
    "scripts/parse_sources.py",
)


class InitializationError(RuntimeError):
    """Raised when a vault cannot be initialized safely."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize an Obsidian research vault for a scientific topic."
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Path of the new vault directory (must not already exist).",
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="Scientific research topic recorded in state/research.md.",
    )
    return parser.parse_args()


def normalize_topic(raw_topic: str) -> str:
    topic = raw_topic.strip()
    if not topic:
        raise InitializationError("The research topic must not be empty.")
    if any(character in topic for character in ("\x00", "\r", "\n")):
        raise InitializationError("The research topic must be a single line of text.")
    return topic


def normalize_target(raw_target: Path) -> Path:
    target = Path(os.path.abspath(raw_target.expanduser()))
    if target == Path(target.anchor):
        raise InitializationError("The filesystem root cannot be used as a vault target.")
    if os.path.lexists(target):
        raise InitializationError(f"Target already exists: {target}")
    if not target.parent.exists():
        raise InitializationError(f"Target parent does not exist: {target.parent}")
    if not target.parent.is_dir():
        raise InitializationError(f"Target parent is not a directory: {target.parent}")
    return target


def validate_assets(assets_dir: Path) -> None:
    required = (*ASSET_FILES, "research.md.template")
    missing = [name for name in required if not (assets_dir / name).is_file()]
    if missing:
        raise InitializationError(
            "The skill installation is missing required assets: " + ", ".join(missing)
        )

    template = (assets_dir / "research.md.template").read_text(encoding="utf-8")
    if template.count("{{TOPIC}}") != 1 or template.count("{{TOPIC_YAML}}") != 1:
        raise InitializationError(
            "research.md.template must contain exactly one {{TOPIC}} placeholder "
            "and one {{TOPIC_YAML}} placeholder."
        )

    for name in ("queue.json", "shortlist.json"):
        try:
            json.loads((assets_dir / name).read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise InitializationError(f"assets/{name} is not valid JSON: {error}") from error

    missing_scripts = [
        name
        for name in (
            "seed_openalex.py",
            "acquire_openalex.py",
            "configure_openalex.py",
            "process_sources.py",
            "parse_sources.py",
        )
        if not (assets_dir.parent / "scripts" / name).is_file()
    ]
    if missing_scripts:
        raise InitializationError(
            "The skill installation is missing scripts: " + ", ".join(missing_scripts)
        )
    if not (assets_dir.parent / "references" / "parsing.md").is_file():
        raise InitializationError("The skill installation is missing references/parsing.md.")


def render_research(template: str, topic: str) -> str:
    replacements = {
        "TOPIC": topic,
        "TOPIC_YAML": json.dumps(topic, ensure_ascii=False),
    }
    return re.sub(
        r"\{\{(TOPIC|TOPIC_YAML)\}\}",
        lambda match: replacements[match.group(1)],
        template,
    )


def populate_vault(vault: Path, assets_dir: Path, topic: str) -> None:
    for directory in REQUIRED_DIRECTORIES:
        (vault / directory).mkdir(parents=True, exist_ok=False)

    for name in (".gitignore", "AGENTS.md", "CLAUDE.md", "sources.base", "wiki.base"):
        shutil.copyfile(assets_dir / name, vault / name)
    shutil.copyfile(assets_dir.parent / "references" / "parsing.md", vault / "PARSING.md")

    research_template = (assets_dir / "research.md.template").read_text(
        encoding="utf-8"
    )
    (vault / "state" / "research.md").write_text(
        render_research(research_template, topic),
        encoding="utf-8",
    )
    shutil.copyfile(assets_dir / "queue.json", vault / "state" / "queue.json")
    shutil.copyfile(
        assets_dir / "shortlist.json", vault / "state" / "shortlist.json"
    )
    (vault / "state" / "candidates.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "topic": topic,
                "target": {"min": 80, "max": 100},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": None,
                "works": {},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (vault / "state" / "search-log.jsonl").touch()
    (vault / "state" / "acquisition.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": None,
                "planned_at": None,
                "shortlist_fingerprint": None,
                "content_price_usd": "0.01",
                "works": {},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (vault / "state" / "parsing.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": None,
                "configuration": {},
                "works": {},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    shutil.copyfile(
        assets_dir / "source-note.md", vault / "templates" / "source-note.md"
    )
    shutil.copyfile(
        assets_dir / "wiki-entry.md", vault / "templates" / "wiki-entry.md"
    )
    for name in (
        "seed_openalex.py",
        "acquire_openalex.py",
        "configure_openalex.py",
        "process_sources.py",
        "parse_sources.py",
    ):
        destination = vault / "scripts" / name
        shutil.copyfile(assets_dir.parent / "scripts" / name, destination)
        destination.chmod(0o755)


def validate_vault(vault: Path, assets_dir: Path, topic: str) -> None:
    missing_directories = [
        name for name in REQUIRED_DIRECTORIES if not (vault / name).is_dir()
    ]
    missing_files = [name for name in REQUIRED_FILES if not (vault / name).is_file()]
    if missing_directories or missing_files:
        details = []
        if missing_directories:
            details.append("directories: " + ", ".join(missing_directories))
        if missing_files:
            details.append("files: " + ", ".join(missing_files))
        raise InitializationError("Vault validation failed; missing " + "; ".join(details))

    research_text = (vault / "state" / "research.md").read_text(encoding="utf-8")
    research_template = (assets_dir / "research.md.template").read_text(encoding="utf-8")
    if research_text != render_research(research_template, topic):
        raise InitializationError("The research topic was not rendered correctly.")

    try:
        queue = json.loads((vault / "state" / "queue.json").read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise InitializationError(f"state/queue.json is not valid JSON: {error}") from error
    if queue != []:
        raise InitializationError("state/queue.json must start as an empty JSON array.")

    try:
        shortlist = json.loads(
            (vault / "state" / "shortlist.json").read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as error:
        raise InitializationError(
            f"state/shortlist.json is not valid JSON: {error}"
        ) from error
    if shortlist != []:
        raise InitializationError("state/shortlist.json must start as an empty JSON array.")

    try:
        candidates = json.loads(
            (vault / "state" / "candidates.json").read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as error:
        raise InitializationError(
            f"state/candidates.json is not valid JSON: {error}"
        ) from error
    if candidates.get("topic") != topic or candidates.get("target") != {
        "min": 80,
        "max": 100,
    }:
        raise InitializationError("state/candidates.json was not initialized correctly.")
    if candidates.get("works") != {}:
        raise InitializationError("state/candidates.json must start without works.")
    if (vault / "state" / "search-log.jsonl").read_text(encoding="utf-8"):
        raise InitializationError("state/search-log.jsonl must start empty.")

    try:
        acquisition = json.loads(
            (vault / "state" / "acquisition.json").read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as error:
        raise InitializationError(
            f"state/acquisition.json is not valid JSON: {error}"
        ) from error
    if acquisition.get("schema_version") != 1 or acquisition.get("works") != {}:
        raise InitializationError("state/acquisition.json was not initialized correctly.")

    try:
        parsing = json.loads(
            (vault / "state" / "parsing.json").read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as error:
        raise InitializationError(
            f"state/parsing.json is not valid JSON: {error}"
        ) from error
    if parsing.get("schema_version") != 1 or parsing.get("works") != {}:
        raise InitializationError("state/parsing.json was not initialized correctly.")


def initialize_vault(target: Path, topic: str, assets_dir: Path) -> None:
    temporary_path: Path | None = None
    try:
        temporary_path = Path(
            tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent)
        )
        populate_vault(temporary_path, assets_dir, topic)
        validate_vault(temporary_path, assets_dir, topic)

        if os.path.lexists(target):
            raise InitializationError(f"Target appeared during initialization: {target}")
        temporary_path.rename(target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            shutil.rmtree(temporary_path, ignore_errors=True)


def main() -> int:
    args = parse_args()
    try:
        topic = normalize_topic(args.topic)
        target = normalize_target(args.target)
        assets_dir = Path(__file__).resolve().parent.parent / "assets"
        validate_assets(assets_dir)
        initialize_vault(target, topic, assets_dir)
    except (InitializationError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Created research vault: {target}")
    print("Open Obsidian, choose 'Open folder as vault', and select that directory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
