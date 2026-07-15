#!/usr/bin/env python3
"""Securely store an OpenAlex API key for all research-vault tasks."""

from __future__ import annotations

import argparse
from getpass import getpass
import os
from pathlib import Path
import sys
import tempfile


class ConfigurationError(RuntimeError):
    """Raised when the credential cannot be configured safely."""


def config_path() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".config"
    return Path(os.path.abspath(base)) / "research-vault" / ".env"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prompt for and securely store an OpenAlex API key."
    )
    parser.add_argument(
        "--from-env-file",
        type=Path,
        help="Import OPEN_ALEX from an existing .env file without printing it.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing research-vault credential.",
    )
    return parser.parse_args()


def normalize_key(raw: str) -> str:
    key = raw.strip()
    if not key:
        raise ConfigurationError("The OpenAlex API key must not be empty.")
    if any(character.isspace() for character in key) or "\x00" in key:
        raise ConfigurationError("The OpenAlex API key must not contain whitespace.")
    return key


def key_from_env_file(path: Path) -> str:
    source = Path(os.path.abspath(path.expanduser()))
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ConfigurationError(f"Could not read {source}: {error}") from error
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, value = line.split("=", 1)
        if name.strip() in {"OPEN_ALEX", "OPENALEX_API_KEY"}:
            return normalize_key(value.strip().strip('"').strip("'"))
    raise ConfigurationError(f"No OpenAlex API key was found in {source}.")


def write_key(path: Path, key: str, force: bool) -> None:
    if path.exists() and not force:
        raise ConfigurationError(
            f"A credential already exists at {path}. Pass --force to replace it."
        )
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=".env.tmp-")
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"OPEN_ALEX={key}\n")
        temporary.replace(path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    destination = config_path()
    try:
        key = (
            key_from_env_file(args.from_env_file)
            if args.from_env_file
            else normalize_key(getpass("OpenAlex API key: "))
        )
        write_key(destination, key, args.force)
    except (ConfigurationError, EOFError, KeyboardInterrupt, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(f"Saved OpenAlex credential to {destination}")
    print("Future research-vault tasks will discover it automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
