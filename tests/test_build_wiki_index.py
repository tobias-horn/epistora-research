#!/usr/bin/env python3
"""Regression tests for the derived research-vault claim index."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_wiki_index", ROOT / "research-vault" / "scripts" / "build_wiki_index.py"
)
assert SPEC and SPEC.loader
INDEXER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INDEXER)


SOURCE = """---
type: source
title: Paper A
aliases: []
openalex_id: W1
study_id: study-a
concepts: ["[[Appropriate reliance]]"]
facets: [human-ai-interaction]
---
# Paper A

## Main claims and evidence

### C1 — Main result

- **Claim:** Assistance improved accuracy in the tested task. ^c-w1-01
- **Evidence or reasoning:** Randomized between-group comparison.
- **Scope and conditions:** Adult participants in one classification task.
- **Locator:** Results > Main analysis, p. 7
- **Evidence type:** primary-result
"""


WIKI = """---
type: wiki
wiki_id: appropriate-reliance
title: Appropriate reliance
aliases: []
facets: [human-ai-interaction]
kind: concept
status: developed
description: Matching reliance to whether advice is correct.
sources:
  - "[[Paper A]]"
---
# Appropriate reliance

## Propositions

### P1 — Performance is conditional

- **Statement:** Assistance can improve accuracy in some tasks. ^p-appropriate-reliance-01
- **Evidence pattern:** sparse
- **Assessment:** One directly relevant experiment; generalization is uncertain.
- **Scope:** The tested classification task and participant population.
- **Supports:** [[Paper A#^c-w1-01|Paper A, C1]]
- **Challenges:**
- **Qualifies:**
- **Update triggers:** Replication in another task or a comparative synthesis.

## Connections

"""


class WikiIndexTests(unittest.TestCase):
    def make_vault(self, root: Path, wiki: str = WIKI) -> Path:
        (root / "sources").mkdir()
        (root / "wiki").mkdir()
        (root / "sources" / "Paper A.md").write_text(SOURCE, encoding="utf-8")
        (root / "wiki" / "Appropriate reliance.md").write_text(wiki, encoding="utf-8")
        return root

    def test_builds_claim_proposition_and_evidence_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index, summary = INDEXER.inspect_vault(self.make_vault(Path(directory)))

            self.assertEqual(summary["errors"], [])
            self.assertEqual(summary["source_claims"], 1)
            self.assertEqual(summary["wiki_propositions"], 1)
            proposition = next(
                item for item in index if item["record_type"] == "wiki-proposition"
            )
            self.assertEqual(proposition["id"], "p-appropriate-reliance-01")
            self.assertEqual(proposition["evidence"][0]["claim_id"], "c-w1-01")
            self.assertEqual(proposition["facets"], ["human-ai-interaction"])
            claim = next(item for item in index if item["record_type"] == "source-claim")
            self.assertEqual(claim["evidence_type"], "primary-result")
            self.assertEqual(claim["facets"], ["human-ai-interaction"])

    def test_dotted_titles_are_not_mistaken_for_file_extensions(self) -> None:
        self.assertEqual(
            INDEXER.normalized_target("Author et al. 2025 — Result.md"),
            "author et al. 2025 — result",
        )

    def test_rejects_missing_cited_claim_and_property_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            broken = WIKI.replace("#^c-w1-01", "#^c-w1-99").replace(
                '  - "[[Paper A]]"', '  - "[[Paper B]]"'
            )
            _, summary = INDEXER.inspect_vault(
                self.make_vault(Path(directory), wiki=broken)
            )
            codes = {item["code"] for item in summary["errors"]}

            self.assertIn("missing-cited-claim", codes)
            self.assertIn("source-property-drift", codes)

    def test_rejects_unknown_relation_and_missing_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            broken = WIKI + "- **resembles** → [[Absent concept]] — vague relation\n"
            _, summary = INDEXER.inspect_vault(
                self.make_vault(Path(directory), wiki=broken)
            )
            codes = {item["code"] for item in summary["errors"]}

            self.assertIn("unknown-relation", codes)
            self.assertIn("missing-relation-target", codes)


if __name__ == "__main__":
    unittest.main()
