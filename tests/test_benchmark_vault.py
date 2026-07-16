#!/usr/bin/env python3
"""Regression tests for the research-vault benchmark helpers."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "benchmark_vault", ROOT / "benchmarks" / "benchmark_vault.py"
)
assert SPEC and SPEC.loader
BENCHMARK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BENCHMARK)


class VaultBenchmarkTests(unittest.TestCase):
    def test_structural_audit_detects_provenance_and_graph_failures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            (vault / "sources").mkdir()
            (vault / "wiki").mkdir()
            (vault / "sources" / "Paper A.md").write_text(
                """---
type: source
title: Paper A
---
# Paper A
### C1 — Result
- **Claim:** A supports X. ^c1
- **Locator:** Results, p. 4
""",
                encoding="utf-8",
            )
            (vault / "wiki" / "Concept X.md").write_text(
                """---
type: wiki
title: Concept X
aliases:
  - X
sources:
  - "[[Paper A]]"
---
# Concept X
### P1 — Evidence
- **Claim:** X occurs. ^p1
- **Supports:** [[Paper A#^c1]]
## Connections
- **contrasts with** → [[Missing concept]] — distinction
""",
                encoding="utf-8",
            )

            result = BENCHMARK.audit_vault(vault)

            self.assertEqual(result["source_claims"], 1)
            self.assertEqual(result["source_claims_with_stable_id"], 1)
            self.assertEqual(result["source_claims_with_locator"], 1)
            self.assertEqual(result["wiki_propositions"], 1)
            self.assertEqual(result["wiki_propositions_with_stable_id"], 1)
            self.assertEqual(
                result["wiki_propositions_with_source_claim_citation"], 1
            )
            self.assertEqual(result["broken_wikilink_count"], 1)
            self.assertEqual(result["typed_connection_ratio"], 1.0)
            self.assertEqual(result["source_property_drift"], [])

    def test_shortlist_audit_reports_balance_without_composite_score(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            shortlist = Path(directory) / "shortlist.json"
            shortlist.write_text(
                json.dumps(
                    [
                        {
                            "title": "A",
                            "publication_year": 2025,
                            "type": "article",
                            "language": "en",
                            "cited_by_count": 10,
                            "roles": ["frontier", "primary-study"],
                            "primary_topic": {"name": "Topic A"},
                            "authors": [
                                {
                                    "id": "A1",
                                    "institutions": [{"id": "I1"}],
                                }
                            ],
                            "has_pdf": True,
                            "has_xml": True,
                            "availability": ["cached-pdf", "cached-xml"],
                            "discovered_by": ["search-1"],
                        },
                        {
                            "title": "B",
                            "publication_year": 2010,
                            "type": "review",
                            "language": "de",
                            "cited_by_count": 100,
                            "roles": ["foundation", "synthesis"],
                            "primary_topic": {"name": "Topic B"},
                            "authors": [
                                {
                                    "id": "A2",
                                    "institutions": [{"id": "I2"}],
                                }
                            ],
                            "has_pdf": True,
                            "has_xml": False,
                            "availability": ["external-pdf"],
                            "discovered_by": ["search-2"],
                        },
                    ]
                ),
                encoding="utf-8",
            )

            result = BENCHMARK.audit_shortlist(shortlist)

            self.assertEqual(result["works"], 2)
            self.assertEqual(result["work_types"]["counts"], {"article": 1, "review": 1})
            self.assertEqual(result["primary_topics"]["normalized_entropy"], 1.0)
            self.assertEqual(result["authors"]["hhi"], 0.5)
            self.assertEqual(result["availability"]["any-pdf"], 2)
            self.assertNotIn("score", result)

    def test_search_log_audit_measures_marginal_yield_and_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "search-log.jsonl"
            log.write_text(
                "\n".join(
                    json.dumps(event)
                    for event in (
                        {
                            "event": "search",
                            "search_id": "s1",
                            "stage": "terminology",
                            "strand": "first",
                            "returned_ids": ["W1", "W2"],
                            "new_candidate_records": 2,
                        },
                        {
                            "event": "search",
                            "search_id": "s2",
                            "stage": "frontier",
                            "strand": "second",
                            "returned_ids": ["W2", "W3"],
                            "new_candidate_records": 1,
                        },
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            result = BENCHMARK.audit_search_log(log)

            self.assertEqual(result["event_count"], 2)
            self.assertEqual(result["cumulative_unique_records"], 3)
            self.assertEqual(result["events"][1]["new_to_sequence"], 1)
            self.assertAlmostEqual(result["pairwise_overlap"][0]["jaccard"], 1 / 3)


if __name__ == "__main__":
    unittest.main()
