#!/usr/bin/env python3
"""Install the local parser runtime and process a finalized research vault."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


PYTHON_VERSION = "3.12"
PACKAGES = ("docling==2.111.0", "lxml==6.1.1")
MANIFEST_VERSION = 1


class ProcessError(RuntimeError):
    """Raised when the parser runtime or processing command fails."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_vault(raw: Path) -> Path:
    vault = Path(os.path.abspath(raw.expanduser()))
    required = (vault / "state" / "queue.json", vault / "scripts" / "parse_sources.py")
    if not vault.is_dir() or any(not path.is_file() for path in required):
        raise ProcessError(f"Not an initialized research vault: {vault}")
    return vault


def runtime_paths(vault: Path) -> tuple[Path, Path, Path, Path]:
    root = vault / ".research-vault"
    environment = root / "parser-env"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return environment, python, root / "cache", root / "parser-env.json"


def expected_lock() -> dict[str, object]:
    return {
        "manifest_version": MANIFEST_VERSION,
        "python": PYTHON_VERSION,
        "packages": list(PACKAGES),
    }


def lock_hash() -> str:
    encoded = json.dumps(expected_lock(), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_manifest(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def cache_environment(cache: Path) -> dict[str, str]:
    environment = os.environ.copy()
    mappings = {
        "XDG_CACHE_HOME": cache / "xdg",
        "HF_HOME": cache / "huggingface",
        "TORCH_HOME": cache / "torch",
        "DOCLING_CACHE_DIR": cache / "docling",
    }
    for key, path in mappings.items():
        path.mkdir(parents=True, exist_ok=True)
        environment[key] = str(path)
    environment.setdefault("TOKENIZERS_PARALLELISM", "false")
    return environment


def healthy(python: Path, cache: Path) -> bool:
    if not python.is_file():
        return False
    check = subprocess.run(
        [str(python), "-c", "import docling, lxml"],
        env=cache_environment(cache),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return check.returncode == 0


def install_runtime(vault: Path) -> tuple[Path, dict[str, str]]:
    environment, python, cache, manifest_path = runtime_paths(vault)
    manifest = load_manifest(manifest_path)
    if manifest.get("lock_sha256") == lock_hash() and healthy(python, cache):
        return python, cache_environment(cache)

    environment.parent.mkdir(parents=True, exist_ok=True)
    uv = shutil.which("uv")
    if uv:
        if not python.is_file():
            subprocess.run([uv, "venv", "--python", PYTHON_VERSION, str(environment)], check=True)
        subprocess.run(
            [uv, "pip", "install", "--python", str(python), *PACKAGES],
            env=cache_environment(cache),
            check=True,
        )
        installer = "uv"
    else:
        if not (3, 10) <= sys.version_info[:2] < (3, 15):
            raise ProcessError(
                "Install uv, or run this command with Python 3.10–3.14 so a local "
                "virtual environment can be created."
            )
        if not python.is_file():
            subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
        subprocess.run(
            [str(python), "-m", "pip", "install", *PACKAGES],
            env=cache_environment(cache),
            check=True,
        )
        installer = "venv+pip"

    if not healthy(python, cache):
        raise ProcessError("The local parser environment failed its import check.")
    versions = subprocess.run(
        [
            str(python),
            "-c",
            (
                "import lxml; from importlib.metadata import version; "
                "print(version('docling')); print(lxml.__version__)"
            ),
        ],
        env=cache_environment(cache),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    manifest = {
        **expected_lock(),
        "lock_sha256": lock_hash(),
        "installed_at": utc_now(),
        "installer": installer,
        "environment": str(environment.relative_to(vault)),
        "cache": str(cache.relative_to(vault)),
        "platform": platform.platform(),
        "resolved": {"docling": versions[0], "lxml": versions[1]},
    }
    temporary = manifest_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    print(f"Installed the vault-local parser environment in {environment}")
    return python, cache_environment(cache)


def process(vault: Path, force: bool) -> None:
    python, environment = install_runtime(vault)
    command = [str(python), str(vault / "scripts" / "parse_sources.py"), str(vault)]
    if force:
        command.append("--force")
    completed = subprocess.run(command, env=environment, check=False)
    if completed.returncode:
        raise ProcessError(f"Source processing exited with status {completed.returncode}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process finalized XML/PDF sources into clean Markdown."
    )
    parser.add_argument("vault", type=Path)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild existing Markdown outputs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        process(normalize_vault(args.vault), args.force)
    except (ProcessError, OSError, subprocess.SubprocessError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
