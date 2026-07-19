#!/usr/bin/env python3
"""Regression tests for source-selection access policies."""

from __future__ import annotations

from argparse import Namespace
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "seed_openalex", ROOT / "research-vault" / "scripts" / "seed_openalex.py"
)
assert SPEC and SPEC.loader
SEEDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SEEDER)


class SeedAccessPolicyTests(unittest.TestCase):
    def test_grouping_can_be_scoped_to_a_campaign(self) -> None:
        works = {
            "https://openalex.org/W1": {
                "version_key": "title:w1",
                "discovered_by": [{"search_id": "s1", "campaign": "baseline"}],
            },
            "https://openalex.org/W2": {
                "version_key": "title:w2",
                "discovered_by": [{"search_id": "s2", "campaign": "recent"}],
            },
        }

        groups = SEEDER.grouped_candidates(works, "recent")

        self.assertEqual(list(groups), ["title:w2"])

    def test_shortlist_records_evidentially_selected_access_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            (vault / "state").mkdir()
            (vault / "state" / "topic.md").write_text("# Topic\n")
            (vault / "state" / "queue.json").write_text("[]\n")
            works = {
                "https://openalex.org/W1": {
                    "metadata": {
                        "openalex_id": "https://openalex.org/W1",
                        "title": "Relevant but inaccessible",
                        "available_content": False,
                    },
                    "version_key": "title:w1",
                    "screening": {
                        "label": "core",
                        "reason": "Directly eligible evidence.",
                        "roles": ["primary-study"],
                        "terms": [],
                    },
                    "selected": True,
                    "discovered_by": [{"search_id": "s1", "campaign": "baseline"}],
                },
                "https://openalex.org/W2": {
                    "metadata": {
                        "openalex_id": "https://openalex.org/W2",
                        "title": "Relevant and accessible",
                        "available_content": True,
                        "availability": ["cached-xml"],
                    },
                    "version_key": "title:w2",
                    "screening": {
                        "label": "core",
                        "reason": "Directly eligible evidence.",
                        "roles": ["primary-study"],
                        "terms": [],
                    },
                    "selected": True,
                    "discovered_by": [{"search_id": "s1", "campaign": "baseline"}],
                },
            }
            (vault / "state" / "candidates.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "topic": "test",
                        "target": {"min": 1, "max": 2},
                        "active_campaign": "baseline",
                        "campaigns": {
                            "baseline": {
                                "name": "Baseline topic map",
                                "purpose": "Initial coverage",
                                "core_phrase": None,
                            }
                        },
                        "works": works,
                    }
                )
            )

            SEEDER.command_shortlist(
                Namespace(
                    vault=vault,
                    min_papers=1,
                    max_papers=2,
                    allow_outside_target=False,
                )
            )

            shortlist = json.loads((vault / "state" / "shortlist.json").read_text())
            gaps = json.loads((vault / "state" / "access-gaps.json").read_text())
            self.assertEqual([item["title"] for item in shortlist], ["Relevant and accessible"])
            self.assertEqual(len(gaps), 1)
            self.assertEqual(gaps[0]["selected_ids"], ["https://openalex.org/W1"])
            self.assertEqual(shortlist[0]["campaign"], "baseline")

    def test_campaign_command_creates_and_selects_campaign(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            (vault / "state").mkdir()
            (vault / "state" / "topic.md").write_text("# Topic\n")
            (vault / "state" / "queue.json").write_text("[]\n")
            (vault / "state" / "candidates.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "topic": "test",
                        "target": {"min": 80, "max": 100},
                        "active_campaign": "baseline",
                        "campaigns": {
                            "baseline": {
                                "name": "Baseline topic map",
                                "purpose": "Initial coverage",
                                "core_phrase": None,
                            }
                        },
                        "works": {},
                    }
                )
            )

            SEEDER.command_campaign(
                Namespace(
                    vault=vault,
                    id="recent-methods",
                    name="Recent methods",
                    purpose="Extend method coverage",
                )
            )

            state = json.loads((vault / "state" / "candidates.json").read_text())
            self.assertEqual(state["active_campaign"], "recent-methods")
            self.assertEqual(
                state["campaigns"]["recent-methods"]["purpose"],
                "Extend method coverage",
            )


if __name__ == "__main__":
    unittest.main()
