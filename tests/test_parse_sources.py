#!/usr/bin/env python3
"""Focused regression tests for the research-vault XML parser."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "parse_sources", ROOT / "research-vault" / "scripts" / "parse_sources.py"
)
assert SPEC and SPEC.loader
PARSER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PARSER)


class XMLParserTests(unittest.TestCase):
    def parse(self, xml: str, title: str = "Test Paper") -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper.xml"
            path.write_text(xml, encoding="utf-8")
            return PARSER.parse_xml(
                path,
                "W123",
                {"openalex_id": "https://openalex.org/W123", "title": title},
            )

    def test_canonical_tei_preserves_structured_objects(self) -> None:
        result = self.parse(
            """<TEI xmlns="http://www.tei-c.org/ns/1.0">
            <teiHeader><fileDesc><titleStmt><title type="main">Test Paper</title></titleStmt>
            <sourceDesc><biblStruct><analytic><author><persName>Ada Lovelace</persName></author></analytic></biblStruct></sourceDesc>
            </fileDesc><profileDesc><abstract>Abstract text.</abstract></profileDesc></teiHeader>
            <text><body><div xml:id="s1"><head>Methods</head>
            <p>See <ref type="bibr" target="#b0">[1]</ref>.</p>
            <formula xml:id="f1">E = mc2</formula>
            <figure xml:id="g1"><label>1</label><figDesc>A diagram</figDesc><graphic coords="1,2,3,4"/></figure>
            <figure type="table"><table><row><cell>A</cell><cell>B</cell></row><row><cell>1</cell><cell>2</cell></row></table></figure>
            </div></body><back><div type="references"><listBibl><biblStruct xml:id="b0"><note type="raw_reference">Reference one.</note></biblStruct></listBibl></div></back></text>
            </TEI>"""
        )
        self.assertEqual(len(result["sections"]), 1)
        self.assertEqual(len(result["tables"]), 1)
        self.assertEqual(len(result["figures"]), 1)
        self.assertEqual(len(result["formulas"]), 1)
        self.assertFalse(result["formulas"][0]["latex_validated"])
        self.assertEqual(result["references"][0]["xml_id"], "b0")

    def test_html_wrapped_lowercase_flat_tei(self) -> None:
        result = self.parse(
            """<html><body><tei><teiheader><filedesc><titlestmt><title type="main">Test Paper</title></titlestmt></filedesc></teiheader>
            <text><front/><div>Introduction<p>This is flat OpenAlex text with meaningful parser words.</p></div><back/></text>
            </tei></body></html>"""
        )
        self.assertEqual(result["content_mode"], "flat-text")
        self.assertIn("html-wrapper", result["quality"]["issues"])
        self.assertEqual(result["sections"][0]["heading_source"], "div-text")

    def test_malformed_xml_uses_recovery_and_flags_it(self) -> None:
        result = self.parse(
            "<TEI><teiHeader><title>Test Paper</title></teiHeader><text><body><div><head>Results</head><p>Recovered paragraph<div></body></text></TEI>"
        )
        self.assertTrue(result["parser"]["recovered"])
        self.assertIn("xml-recovery-used", result["quality"]["issues"])

    def test_external_entity_is_not_resolved(self) -> None:
        result = self.parse(
            """<!DOCTYPE TEI [<!ENTITY secret SYSTEM "file:///etc/passwd">]>
            <TEI><teiHeader><title>Test Paper</title></teiHeader><text><body><div><head>Safe</head><p>&secret;</p></div></body></text></TEI>"""
        )
        self.assertNotIn("root:", result["markdown"])
        self.assertNotIn("/bin/", result["markdown"])

    def test_unknown_private_glyph_is_explicit(self) -> None:
        result = self.parse(
            "<TEI><teiHeader><title>Test Paper</title></teiHeader><text><body><div><head>Text</head><p>A\ue222B</p></div></body></text></TEI>"
        )
        self.assertIn("⟦U+E222⟧", result["markdown"])

    def test_metadata_title_mismatch_is_routed_for_review(self) -> None:
        result = self.parse(
            "<TEI><teiHeader><title>Completely Different Work</title></teiHeader><text><body><div><head>Text</head><p>Body.</p></div></body></text></TEI>",
            title="Target Scientific Study",
        )
        self.assertIn("probable-content-identity-mismatch", result["quality"]["issues"])

    def test_finalized_queue_is_the_only_parser_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            raw = vault / "raw" / "works" / "W123"
            raw.mkdir(parents=True)
            source = raw / "fulltext.tei.xml"
            source.write_text("<TEI/>", encoding="utf-8")
            (vault / "state").mkdir()
            (vault / "state" / "queue.json").write_text(
                json.dumps(
                    [
                        {
                            "openalex_id": "https://openalex.org/W123",
                            "title": "Queued work",
                            "artifacts": {"xml": "raw/works/W123/fulltext.tei.xml"},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            records, order = PARSER.source_records(vault)
            self.assertEqual(order, ["W123"])
            self.assertEqual(records["W123"]["artifacts"]["xml"], str(source))

    def test_broken_xml_falls_back_to_available_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            vault = Path(directory)
            work = vault / "raw" / "works" / "W123"
            work.mkdir(parents=True)
            (work / "fulltext.tei.xml").write_text("<not-tei/>", encoding="utf-8")
            (work / "paper.pdf").write_bytes(b"%PDF-1.4 fixture")
            state = vault / "state"
            state.mkdir()
            (state / "queue.json").write_text(
                json.dumps(
                    [
                        {
                            "openalex_id": "https://openalex.org/W123",
                            "title": "Fallback work",
                            "artifacts": {
                                "xml": "raw/works/W123/fulltext.tei.xml",
                                "pdf": "raw/works/W123/paper.pdf",
                            },
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (state / "parsing.json").write_text(
                json.dumps({"schema_version": 1, "works": {}}), encoding="utf-8"
            )

            original = PARSER.parse_pdf

            def fake_parse_pdf(
                path: Path, temporary_root: Path, converter: object | None
            ):
                del temporary_root
                return (
                    {
                        "format": "pdf",
                        "parser": {"name": "docling", "version": "test"},
                        "source": {
                            "path": PARSER.recorded_source_path(path),
                            "sha256": PARSER.sha256_file(path),
                            "bytes": path.stat().st_size,
                        },
                        "markdown": "# Fallback work\n\nPDF text.\n",
                        "quality": {"score": 1.0, "issues": [], "words": 2},
                        "elapsed_seconds": 0.01,
                    },
                    converter,
                )

            PARSER.parse_pdf = fake_parse_pdf
            try:
                PARSER.command_parse(SimpleNamespace(vault=vault, force=False))
            finally:
                PARSER.parse_pdf = original

            parsing = json.loads((state / "parsing.json").read_text(encoding="utf-8"))
            result = parsing["works"]["W123"]
            self.assertEqual(result["status"], "parsed")
            self.assertEqual(result["primary"], "pdf")
            self.assertIn("xml", result["input_errors"])
            self.assertEqual(result["output"], "markdown/W123.md")
            self.assertEqual(
                (vault / "markdown" / "W123.md").read_text(encoding="utf-8"),
                "# Fallback work\n\nPDF text.\n",
            )
            self.assertFalse((vault / "derived").exists())

    def test_docling_runs_only_for_unusable_xml(self) -> None:
        usable = {"quality": {"issues": ["formula-text-requires-pdf-validation"]}}
        broken = {"quality": {"issues": ["missing-main-text"]}}
        self.assertFalse(PARSER.parser_converter_needed(True, True, usable))
        self.assertTrue(PARSER.parser_converter_needed(True, True, broken))
        self.assertTrue(PARSER.parser_converter_needed(False, True, None))


if __name__ == "__main__":
    unittest.main()
