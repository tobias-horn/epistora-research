#!/usr/bin/env python3
"""Regression tests for complete vault initialization."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "init_vault", ROOT / "research-vault" / "scripts" / "init_vault.py"
)
assert SPEC and SPEC.loader
INITIALIZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INITIALIZER)


class VaultInitializationTests(unittest.TestCase):
    def test_initializer_includes_wiki_workflow_and_indexer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "vault"
            assets = ROOT / "research-vault" / "assets"

            INITIALIZER.initialize_vault(target, "A test research topic", assets)

            self.assertTrue((target / "WIKI.md").is_file())
            self.assertTrue((target / "scripts" / "build_wiki_index.py").is_file())
            self.assertEqual((target / "state" / "access-gaps.json").read_text(), "[]\n")
            self.assertIn("wiki_id:", (target / "templates" / "wiki-entry.md").read_text())
            self.assertIn(
                "state/wiki-index.jsonl", (target / ".gitignore").read_text()
            )


if __name__ == "__main__":
    unittest.main()
