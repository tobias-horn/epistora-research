#!/usr/bin/env python3
"""Regression tests for the isolated parser bootstrap."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "process_sources", ROOT / "research-vault" / "scripts" / "process_sources.py"
)
assert SPEC and SPEC.loader
PROCESS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROCESS)


class RuntimeEnvironmentTests(unittest.TestCase):
    def test_runtime_paths_and_caches_remain_inside_vault(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            cache = vault / ".research-vault" / "cache"
            with mock.patch.dict(
                os.environ,
                {"OPEN_ALEX": "secret-one", "OPENALEX_API_KEY": "secret-two"},
                clear=False,
            ):
                environment = PROCESS.cache_environment(cache)

            self.assertNotIn("OPEN_ALEX", environment)
            self.assertNotIn("OPENALEX_API_KEY", environment)
            self.assertEqual(environment["UV_CACHE_DIR"], str(cache / "uv"))
            self.assertEqual(
                environment["UV_PYTHON_INSTALL_DIR"],
                str(vault / ".research-vault" / "python"),
            )
            self.assertEqual(
                environment["UV_PYTHON_BIN_DIR"],
                str(vault / ".research-vault" / "python-bin"),
            )
            self.assertEqual(environment["PIP_CACHE_DIR"], str(cache / "pip"))
            self.assertEqual(environment["UV_NO_CONFIG"], "1")
            for key in (
                "XDG_CACHE_HOME",
                "HF_HOME",
                "TORCH_HOME",
                "DOCLING_CACHE_DIR",
                "PIP_CACHE_DIR",
                "UV_CACHE_DIR",
                "UV_PYTHON_INSTALL_DIR",
                "UV_PYTHON_BIN_DIR",
            ):
                self.assertTrue(Path(environment[key]).is_relative_to(vault))

    def test_uv_bootstrap_receives_the_isolated_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            completed = SimpleNamespace(stdout="2.111.0\n6.1.1\n")
            with (
                mock.patch.object(PROCESS.shutil, "which", return_value="/usr/bin/uv"),
                mock.patch.object(PROCESS, "healthy", return_value=True),
                mock.patch.object(PROCESS.platform, "platform", return_value="test-platform"),
                mock.patch.object(PROCESS.subprocess, "run", return_value=completed) as run,
                mock.patch.dict(os.environ, {"OPEN_ALEX": "secret"}, clear=False),
            ):
                _python, environment = PROCESS.install_runtime(vault)

            self.assertNotIn("OPEN_ALEX", environment)
            uv_calls = [
                call
                for call in run.call_args_list
                if call.args and call.args[0] and call.args[0][0] == "/usr/bin/uv"
            ]
            self.assertEqual(len(uv_calls), 2)
            self.assertEqual(uv_calls[0].args[0][3], PROCESS.sys.executable)
            for call in uv_calls:
                child_environment = call.kwargs["env"]
                self.assertNotIn("OPEN_ALEX", child_environment)
                self.assertTrue(
                    Path(child_environment["UV_CACHE_DIR"]).is_relative_to(vault)
                )
                self.assertTrue(
                    Path(child_environment["UV_PYTHON_INSTALL_DIR"]).is_relative_to(vault)
                )

            manifest = PROCESS.load_manifest(
                vault / ".research-vault" / "parser-env.json"
            )
            self.assertEqual(
                manifest["uv_python_install_dir"], ".research-vault/python"
            )


if __name__ == "__main__":
    unittest.main()
