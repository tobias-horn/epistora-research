#!/usr/bin/env python3
"""Parse acquired XML/PDF papers into provenance-rich, LLM-native artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys
import tempfile
import time
import unicodedata

from lxml import etree


XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
WORD_RE = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)?")
KNOWN_GLYPHS = str.maketrans(
    {"\ue103": "fi", "\ue09d": "ft", "\ue104": "fl", "\ue0d5": "—", "\ue09a": "fj"}
)
SEVERE_XML_ISSUES = {
    "missing-main-text",
    "very-short-main-text",
    "missing-section-structure",
    "xml-recovery-used",
}


class ParseError(RuntimeError):
    """Raised when parser input or output violates the vault contract."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recorded_source_path(path: Path) -> str:
    """Prefer a vault-relative raw path while keeping non-vault fixtures usable."""
    parts = path.resolve().parts
    raw_positions = [index for index, part in enumerate(parts) if part == "raw"]
    if raw_positions:
        return Path(*parts[raw_positions[-1]:]).as_posix()
    return str(path.resolve())


def normalize_vault(raw: Path) -> Path:
    vault = Path(os.path.abspath(raw.expanduser()))
    if not vault.is_dir() or not (vault / "state" / "queue.json").is_file():
        raise ParseError(f"Not an initialized research vault: {vault}")
    return vault


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ParseError(f"Required file is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise ParseError(f"Invalid JSON in {path}: {error}") from error


def normalize_work_id(raw: object) -> str:
    identifier = str(raw or "").strip().rstrip("/").rsplit("/", 1)[-1].upper()
    if not re.fullmatch(r"W\d+", identifier):
        raise ParseError(f"Invalid OpenAlex work ID: {raw}")
    return identifier


def source_records(vault: Path) -> tuple[dict[str, dict[str, object]], list[str]]:
    queue = load_json(vault / "state" / "queue.json")
    if not isinstance(queue, list) or not queue:
        raise ParseError(
            "state/queue.json is empty. Finalize acquisition before processing sources."
        )
    records: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for item in queue:
        if not isinstance(item, dict):
            continue
        identifier = normalize_work_id(item.get("openalex_id"))
        queued_artifacts = item.get("artifacts")
        if not isinstance(queued_artifacts, dict):
            raise ParseError(f"Queue entry {identifier} has no artifacts map.")
        artifacts = {
            content_format: str(vault / str(queued_artifacts[content_format]))
            for content_format in ("xml", "pdf")
            if queued_artifacts.get(content_format)
            and (vault / str(queued_artifacts[content_format])).is_file()
        }
        if not artifacts:
            raise ParseError(f"Queue entry {identifier} has no readable PDF or XML file.")
        records[identifier] = {"metadata": item, "artifacts": artifacts}
        order.append(identifier)
    return records, order


def local_name(element: etree._Element) -> str:
    if not isinstance(element.tag, str):
        return "entity"
    return etree.QName(element).localname.lower()


def descendants(element: etree._Element | None, name: str) -> list[etree._Element]:
    if element is None:
        return []
    wanted = name.lower()
    return [item for item in element.iter() if local_name(item) == wanted]


def first_descendant(element: etree._Element | None, name: str) -> etree._Element | None:
    if element is None:
        return None
    wanted = name.lower()
    return next((item for item in element.iter() if local_name(item) == wanted), None)


def normalize_space(value: str) -> str:
    value = value.translate(KNOWN_GLYPHS)
    value = "".join(
        f"⟦U+{ord(character):04X}⟧" if 0xE000 <= ord(character) <= 0xF8FF else character
        for character in value
    )
    return " ".join(value.split())


def element_text(element: etree._Element | None) -> str:
    return normalize_space(" ".join(element.itertext())) if element is not None else ""


def direct_text(element: etree._Element) -> str:
    return normalize_space(element.text or "")


def tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return [token for token in WORD_RE.findall(normalized) if len(token) > 1]


def plain_markdown(markdown: str) -> str:
    value = re.sub(r"```.*?```", " ", markdown, flags=re.DOTALL)
    value = re.sub(r"!\[[^]]*\]\([^)]+\)", " ", value)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"[`*_>#|~$\\{}\[\]()]", " ", value)


def overlap(left: str, right: str) -> dict[str, float]:
    left_counts, right_counts = Counter(tokens(left)), Counter(tokens(right))
    matched = sum((left_counts & right_counts).values())
    precision = matched / sum(left_counts.values()) if left_counts else 0.0
    recall = matched / sum(right_counts.values()) if right_counts else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"xml_coverage_by_pdf": precision, "pdf_coverage_by_xml": recall, "f1": f1}


def find_tei(root: etree._Element) -> etree._Element:
    if local_name(root) == "tei":
        return root
    result = first_descendant(root, "tei")
    if result is None:
        raise ParseError("XML contains no TEI element.")
    return result


def safe_parse_xml(path: Path) -> tuple[etree._Element, etree._Element, bool, list[str]]:
    raw = path.read_bytes()
    strict = etree.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=False)
    issues: list[str] = []
    recovered = False
    try:
        root = etree.fromstring(raw, parser=strict)
    except etree.XMLSyntaxError:
        recovery = etree.XMLParser(resolve_entities=False, no_network=True, recover=True, huge_tree=True)
        root = etree.fromstring(raw, parser=recovery)
        recovered = True
        issues.append("xml-recovery-used")
    return root, find_tei(root), recovered, issues


def main_nodes(tei: etree._Element) -> tuple[list[etree._Element], str]:
    text = first_descendant(tei, "text")
    if text is None:
        return [], "missing-text"
    body = first_descendant(text, "body")
    if body is not None:
        return [body], "tei-body"
    return [child for child in text if local_name(child) not in {"front", "back"}], "flat-text"


def heading_for_div(element: etree._Element) -> tuple[str, str]:
    head = next((child for child in element if local_name(child) == "head"), None)
    if head is not None and element_text(head):
        return element_text(head), "head"
    inferred = direct_text(element)
    if inferred and len(inferred) <= 250:
        return inferred, "div-text"
    kind = normalize_space(element.get("type") or "")
    if kind and kind not in {"references", "acknowledgement", "funding"}:
        return kind.replace("_", " ").title(), "type"
    return "", "none"


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


class XMLBuilder:
    def __init__(self, identifier: str, metadata: dict[str, object]) -> None:
        self.identifier = identifier
        self.metadata = metadata
        self.blocks: list[dict[str, object]] = []
        self.sections: list[dict[str, object]] = []
        self.citations: list[dict[str, object]] = []
        self.references: list[dict[str, object]] = []
        self.figures: list[dict[str, object]] = []
        self.tables: list[dict[str, object]] = []
        self.formulas: list[dict[str, object]] = []
        self.heading_path: list[str] = []

    def next_id(self, prefix: str) -> str:
        return f"{prefix}-{len(getattr(self, {'blk':'blocks','sec':'sections','fig':'figures','tbl':'tables','eq':'formulas'}[prefix])) + 1:04d}"

    def add_block(self, kind: str, markdown: str, text: str, element: etree._Element, **extra: object) -> str:
        block_id = self.next_id("blk")
        self.blocks.append(
            {
                "id": block_id,
                "type": kind,
                "markdown": markdown,
                "text": text,
                "heading_path": list(self.heading_path),
                "source": {
                    "format": "xml",
                    "xml_id": element.get(XML_ID),
                    "coords": element.get("coords"),
                    "element": local_name(element),
                },
                **extra,
            }
        )
        return block_id

    def inline(self, element: etree._Element) -> str:
        parts = [element.text or ""]
        for child in element:
            name = local_name(child)
            if name == "ref":
                label = element_text(child) or "reference"
                target = normalize_space(child.get("target") or "")
                ref_type = normalize_space(child.get("type") or "") or "unknown"
                citation = {
                    "id": f"cit-{len(self.citations) + 1:05d}",
                    "label": label,
                    "target": target or None,
                    "type": ref_type,
                }
                self.citations.append(citation)
                if target.startswith("#") and " " not in target:
                    parts.append(f"[{label}]({target})")
                else:
                    parts.append(label)
            else:
                parts.append(self.inline(child))
            parts.append(child.tail or "")
        return normalize_space("".join(parts))

    def table(self, element: etree._Element) -> None:
        rows: list[list[str]] = []
        for row in descendants(element, "row"):
            cells = [element_text(cell) for cell in row if local_name(cell) == "cell"]
            if cells:
                rows.append(cells)
        table_id = self.next_id("tbl")
        if rows:
            width = max(map(len, rows))
            rows = [row + [""] * (width - len(row)) for row in rows]
            lines = ["| " + " | ".join(map(escape_cell, rows[0])) + " |"]
            lines.append("| " + " | ".join(["---"] * width) + " |")
            lines.extend("| " + " | ".join(map(escape_cell, row)) + " |" for row in rows[1:])
            markdown = "\n".join(lines)
        else:
            markdown = "> **Table (flattened XML text):** " + element_text(element)
        block_id = self.add_block("table", markdown, element_text(element), element, object_id=table_id)
        self.tables.append(
            {
                "id": table_id,
                "block_id": block_id,
                "caption": "",
                "cells": rows,
                "source": {"format": "xml", "xml_id": element.get(XML_ID), "coords": element.get("coords")},
            }
        )

    def figure(self, element: etree._Element) -> None:
        tables = descendants(element, "table")
        caption = element_text(first_descendant(element, "figdesc"))
        label = element_text(first_descendant(element, "label"))
        if tables:
            for table in tables:
                self.table(table)
            return
        figure_id = self.next_id("fig")
        figure_type = normalize_space(element.get("type") or "figure")
        markdown = f"> **{figure_type.title()} {label}:** {caption}".replace("  ", " ").rstrip()
        block_id = self.add_block("figure", markdown, caption, element, object_id=figure_id)
        graphics = descendants(element, "graphic")
        self.figures.append(
            {
                "id": figure_id,
                "block_id": block_id,
                "label": label,
                "caption": caption,
                "image_available": any(g.get("url") or g.get("{http://www.w3.org/1999/xlink}href") for g in graphics),
                "source": {"format": "xml", "xml_id": element.get(XML_ID), "coords": element.get("coords")},
            }
        )

    def formula(self, element: etree._Element) -> None:
        text = element_text(element)
        if not text:
            return
        formula_id = self.next_id("eq")
        markdown = f"> **Equation (raw GROBID text; not validated LaTeX):** {text}"
        block_id = self.add_block("formula", markdown, text, element, object_id=formula_id)
        self.formulas.append(
            {
                "id": formula_id,
                "block_id": block_id,
                "raw": text,
                "representation": "grobid-raw-text",
                "latex_validated": False,
                "source": {"format": "xml", "xml_id": element.get(XML_ID), "coords": element.get("coords")},
            }
        )

    def walk(self, element: etree._Element, level: int = 1) -> None:
        name = local_name(element)
        if name in {"head", "s", "label", "figdesc", "graphic", "table"}:
            return
        if name == "div":
            heading, heading_source = heading_for_div(element)
            prior = list(self.heading_path)
            if heading:
                self.heading_path = prior[: max(0, level - 1)] + [heading]
                section_id = self.next_id("sec")
                self.sections.append(
                    {
                        "id": section_id,
                        "heading": heading,
                        "level": min(6, level + 1),
                        "heading_source": heading_source,
                        "heading_path": list(self.heading_path),
                        "xml_id": element.get(XML_ID),
                    }
                )
                self.add_block("heading", "#" * min(6, level + 1) + " " + heading, heading, element, section_id=section_id)
            for child in element:
                if local_name(child) != "head":
                    self.walk(child, level + 1)
            self.heading_path = prior
            return
        if name == "p":
            text = self.inline(element)
            if text:
                self.add_block("paragraph", text, text, element)
            return
        if name == "formula":
            self.formula(element)
            return
        if name == "figure":
            self.figure(element)
            return
        if name == "list":
            items = [self.inline(item) for item in descendants(element, "item")]
            items = [item for item in items if item]
            if items:
                self.add_block("list", "\n".join(f"- {item}" for item in items), " ".join(items), element)
            return
        if name in {"note", "fw"} and normalize_space(element.get("place") or "") in {"foot", "header", "footer"}:
            return
        for child in element:
            self.walk(child, level)


def xml_markdown(title: str, authors: list[str], abstract: str, blocks: list[dict[str, object]], references: list[dict[str, object]]) -> str:
    lines = [f"# {title}", ""]
    if authors:
        lines.extend(["**Authors:** " + "; ".join(authors), ""])
    if abstract:
        lines.extend(["## Abstract", "", abstract, ""])
    lines.extend(["## Full text", ""])
    lines.extend(str(block["markdown"]) + "\n" for block in blocks)
    if references:
        lines.extend(["## References", ""])
        for reference in references:
            anchor = f'<span id="{reference["xml_id"]}"></span>' if reference.get("xml_id") else ""
            lines.append(f"- {anchor}{reference['text']}")
    markdown = "\n".join(lines).rstrip() + "\n"
    anchors = set(re.findall(r'<span id="([^"]+)"></span>', markdown))
    def unlink(match: re.Match[str]) -> str:
        return match.group(0) if match.group(2) in anchors else match.group(1)
    return re.sub(r"\[([^]]+)\]\(#([^)]+)\)", unlink, markdown)


def parse_xml(path: Path, identifier: str, metadata: dict[str, object]) -> dict[str, object]:
    started = time.perf_counter()
    root, tei, recovered, issues = safe_parse_xml(path)
    header = first_descendant(tei, "teiheader")
    titles = descendants(header, "title")
    title_node = next((item for item in titles if normalize_space(item.get("type") or "").lower() == "main"), titles[0] if titles else None)
    xml_title = element_text(title_node)
    metadata_title = normalize_space(str(metadata.get("title") or ""))
    title = xml_title or metadata_title or "Untitled paper"
    title_tokens = set(tokens(metadata_title))
    xml_title_tokens = set(tokens(xml_title))
    title_recall = (
        len(title_tokens & xml_title_tokens) / len(title_tokens)
        if title_tokens and xml_title_tokens
        else 0.0
    )
    title_precision = (
        len(title_tokens & xml_title_tokens) / len(xml_title_tokens)
        if title_tokens and xml_title_tokens
        else 0.0
    )
    title_f1 = (
        2 * title_precision * title_recall / (title_precision + title_recall)
        if title_precision + title_recall
        else 0.0
    )
    if title_node is None or not xml_title:
        issues.append("missing-main-title")
    elif metadata_title and title_f1 < 0.65:
        issues.append("xml-title-metadata-mismatch")
        title = metadata_title
        if len(title_tokens) >= 2 and title_f1 < 0.35:
            issues.append("probable-content-identity-mismatch")
    authors: list[str] = []
    analytic = first_descendant(first_descendant(header, "sourcedesc"), "analytic")
    if analytic is not None:
        for author in [child for child in analytic if local_name(child) == "author"]:
            name = element_text(first_descendant(author, "persname"))
            if name:
                authors.append(name)
    if not authors:
        issues.append("missing-header-authors")
    abstract = element_text(first_descendant(header, "abstract"))
    if not abstract:
        issues.append("missing-abstract")
    nodes, content_mode = main_nodes(tei)
    builder = XMLBuilder(identifier, metadata)
    for node in nodes:
        builder.walk(node)
    back = first_descendant(first_descendant(tei, "text"), "back")
    for entry in descendants(back, "biblstruct"):
        raw = next((note for note in descendants(entry, "note") if normalize_space(note.get("type") or "").lower() == "raw_reference" and element_text(note)), None)
        text = element_text(raw) or element_text(entry)
        if text:
            builder.references.append({"id": f"ref-{len(builder.references)+1:05d}", "xml_id": entry.get(XML_ID), "text": text})
    body_words = sum(len(tokens(str(block["text"]))) for block in builder.blocks if block["type"] != "heading")
    if not nodes or body_words == 0:
        issues.append("missing-main-text")
    elif body_words < 1000:
        issues.append("very-short-main-text")
    if not builder.sections:
        issues.append("missing-section-structure")
    if not builder.references:
        issues.append("missing-bibliography")
    if builder.formulas:
        issues.append("formula-text-requires-pdf-validation")
    if builder.figures and not any(item["image_available"] for item in builder.figures):
        issues.append("figure-images-require-pdf")
    raw_text = path.read_text(encoding="utf-8", errors="replace")
    if "\ufffd" in raw_text:
        issues.append("replacement-characters")
    if root is not tei:
        issues.append("html-wrapper")
    if content_mode != "tei-body":
        issues.append("flat-or-missing-body")
    score = 1.0
    penalties = {
        "missing-main-text": 0.75, "very-short-main-text": 0.4, "missing-section-structure": 0.2,
        "xml-recovery-used": 0.2, "missing-main-title": 0.05, "missing-header-authors": 0.03,
        "missing-abstract": 0.04, "missing-bibliography": 0.08, "replacement-characters": 0.08,
        "xml-title-metadata-mismatch": 0.08, "probable-content-identity-mismatch": 0.3,
    }
    score = max(0.0, score - sum(penalties.get(issue, 0.0) for issue in set(issues)))
    markdown = xml_markdown(title, authors, abstract, builder.blocks, builder.references)
    if "⟦U+" in markdown:
        issues.append("unmapped-private-use-glyphs")
        score = max(0.0, score - 0.05)
    return {
        "format": "xml",
        "parser": {"name": "research-vault-xml", "version": "1", "lxml": ".".join(map(str, etree.LXML_VERSION)), "recovered": recovered},
        "source": {"path": recorded_source_path(path), "sha256": sha256_file(path), "bytes": path.stat().st_size},
        "metadata": {"title": title, "xml_title": xml_title, "metadata_title": metadata_title, "title_token_precision": round(title_precision, 3), "title_token_recall": round(title_recall, 3), "title_token_f1": round(title_f1, 3), "authors": authors, "abstract": abstract},
        "content_mode": content_mode,
        "blocks": builder.blocks,
        "sections": builder.sections,
        "citations": builder.citations,
        "references": builder.references,
        "figures": builder.figures,
        "tables": builder.tables,
        "formulas": builder.formulas,
        "markdown": markdown,
        "quality": {"score": round(score, 3), "issues": sorted(set(issues)), "words": body_words, "headings": len(builder.sections)},
        "elapsed_seconds": time.perf_counter() - started,
    }


def markdown_features(markdown: str) -> dict[str, int]:
    targets = re.findall(r"\]\(#([^)]+)\)", markdown)
    anchors = set(re.findall(r'<span id="([^"]+)"></span>', markdown))
    return {
        "words": len(tokens(plain_markdown(markdown))),
        "headings": len(re.findall(r"(?m)^#{1,6}\s+", markdown)),
        "tables": len(re.findall(r"(?m)^\|.*\|\s*$", markdown)),
        "images": len(re.findall(r"!\[[^]]*\]\([^)]+\)", markdown)),
        "replacement_characters": markdown.count("\ufffd"),
        "private_use_glyphs": sum(0xE000 <= ord(character) <= 0xF8FF for character in markdown),
        "unknown_glyph_markers": markdown.count("⟦U+"),
        "broken_internal_links": sum(target not in anchors for target in targets),
    }


def parse_pdf(
    path: Path, temporary_root: Path, converter: object | None
) -> tuple[dict[str, object], object]:
    started = time.perf_counter()
    if converter is None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        options = PdfPipelineOptions()
        options.do_ocr = True
        options.do_table_structure = True
        converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    result = converter.convert(path)
    document = result.document
    from docling_core.types.doc import ImageRefMode
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temporary_root) as directory:
        markdown_path = Path(directory) / "paper.md"
        document.save_as_markdown(
            markdown_path,
            image_mode=ImageRefMode.PLACEHOLDER,
        )
        markdown = markdown_path.read_text(encoding="utf-8")
    features = markdown_features(markdown)
    issues: list[str] = []
    if features["words"] < 1000:
        issues.append("very-short-pdf-extraction")
    if features["headings"] == 0:
        issues.append("missing-pdf-section-structure")
    if features["replacement_characters"]:
        issues.append("replacement-characters")
    score = max(0.0, 1.0 - 0.45 * (features["words"] < 1000) - 0.15 * (features["headings"] == 0) - 0.1 * bool(features["replacement_characters"]))
    return {
        "format": "pdf",
        "parser": {"name": "docling", "version": __import__("importlib.metadata", fromlist=["version"]).version("docling")},
        "source": {"path": recorded_source_path(path), "sha256": sha256_file(path), "bytes": path.stat().st_size},
        "markdown": markdown,
        "features": features,
        "quality": {"score": round(score, 3), "issues": issues, **features},
        "elapsed_seconds": time.perf_counter() - started,
    }, converter


def route_sources(xml: dict[str, object] | None, pdf: dict[str, object] | None) -> dict[str, object]:
    if xml is None and pdf is None:
        raise ParseError("No parsed source variant exists.")
    if pdf is None:
        xml_issues = set(xml["quality"]["issues"])
        needs_review = bool(SEVERE_XML_ISSUES & xml_issues) or "probable-content-identity-mismatch" in xml_issues
        return {"primary": "xml", "review_required": needs_review, "reason": "Only XML is available.", "comparison": None}
    if xml is None:
        return {"primary": "pdf", "review_required": False, "reason": "Only PDF is available.", "comparison": None}
    comparison = overlap(plain_markdown(str(xml["markdown"])), plain_markdown(str(pdf["markdown"])))
    xml_quality, pdf_quality = float(xml["quality"]["score"]), float(pdf["quality"]["score"])
    xml_words, pdf_words = int(xml["quality"]["words"]), int(pdf["quality"]["words"])
    severe = bool(SEVERE_XML_ISSUES & set(xml["quality"]["issues"]))
    identity_mismatch = "probable-content-identity-mismatch" in set(xml["quality"]["issues"])
    if identity_mismatch:
        primary = "xml" if xml_quality >= pdf_quality else "pdf"
        reason, review = "XML metadata suggests a possible content-identity mismatch; agent verification is required.", True
    elif severe or xml_quality < 0.55 or (pdf_words > max(1500, xml_words * 1.35) and comparison["pdf_coverage_by_xml"] < 0.78):
        primary, reason, review = "pdf", "XML is incomplete relative to the Docling PDF extraction.", False
    elif xml_quality >= 0.78 and comparison["f1"] >= 0.82:
        primary, reason, review = "xml", "XML has strong structure and agrees with the PDF extraction.", False
    else:
        primary = "xml" if xml_quality >= pdf_quality else "pdf"
        reason = "The variants disagree or have complementary weaknesses; agent review is required."
        review = True
    return {"primary": primary, "review_required": review, "reason": reason, "comparison": comparison}


def write_work(
    output: Path,
    xml: dict[str, object] | None,
    pdf: dict[str, object] | None,
    route: dict[str, object],
) -> dict[str, object]:
    primary = xml if route["primary"] == "xml" else pdf
    assert primary is not None
    canonical = str(primary["markdown"])
    atomic_text(output, canonical)
    sources = {}
    for name, value in (("xml", xml), ("pdf", pdf)):
        if value is not None:
            sources[name] = {
                "parser": value["parser"],
                "source": value["source"],
                "quality": value["quality"],
                "elapsed_seconds": value["elapsed_seconds"],
            }
    return {
        "route": route,
        "sources": sources,
        "validation": markdown_features(canonical),
    }


def parser_converter_needed(
    has_xml: bool, has_pdf: bool, xml: dict[str, object] | None
) -> bool:
    if not has_pdf:
        return False
    if not has_xml or xml is None:
        return True
    issues = set(xml["quality"]["issues"])
    return bool(SEVERE_XML_ISSUES & issues) or "probable-content-identity-mismatch" in issues


def command_parse(args: argparse.Namespace) -> None:
    vault = normalize_vault(args.vault)
    records, order = source_records(vault)
    identifiers = order
    output_root = vault / "markdown"
    output_root.mkdir(parents=True, exist_ok=True)
    temporary_root = vault / ".research-vault" / "docling-work"
    converter: object | None = None
    results: list[dict[str, object]] = []
    state_path = vault / "state" / "parsing.json"
    prior_state = load_json(state_path) if state_path.is_file() else {}
    state_works = prior_state.get("works") if isinstance(prior_state, dict) else {}
    state_works = dict(state_works) if isinstance(state_works, dict) else {}
    failures = 0
    for index, identifier in enumerate(identifiers, 1):
        item = records[identifier]
        metadata = item["metadata"]
        assert isinstance(metadata, dict)
        artifacts = item["artifacts"]
        assert isinstance(artifacts, dict)
        destination = output_root / f"{identifier}.md"
        input_checksums = {
            content_format: sha256_file(Path(str(path)))
            for content_format, path in artifacts.items()
        }
        prior_record = state_works.get(identifier)
        if (
            not args.force
            and destination.is_file()
            and isinstance(prior_record, dict)
            and prior_record.get("status") == "parsed"
            and prior_record.get("input_sha256") == input_checksums
        ):
            record = dict(prior_record)
            record["reused"] = True
            record["elapsed_seconds"] = 0.0
            results.append(record)
            print(f"[{index:03d}/{len(identifiers):03d}] {identifier} unchanged")
            continue
        xml: dict[str, object] | None = None
        pdf: dict[str, object] | None = None
        input_errors: dict[str, str] = {}
        try:
            if "xml" in artifacts:
                try:
                    xml = parse_xml(Path(str(artifacts["xml"])), identifier, metadata)
                except Exception as error:
                    input_errors["xml"] = f"{type(error).__name__}: {error}"
            if parser_converter_needed("xml" in artifacts, "pdf" in artifacts, xml):
                pdf_source = Path(str(artifacts["pdf"]))
                try:
                    pdf, converter = parse_pdf(pdf_source, temporary_root, converter)
                except Exception as error:
                    input_errors["pdf"] = f"{type(error).__name__}: {error}"
            route = route_sources(xml, pdf)
            diagnostics = write_work(
                destination, xml, pdf, route
            )
            elapsed = (float(xml["elapsed_seconds"]) if xml else 0.0) + (
                float(pdf["elapsed_seconds"]) if pdf else 0.0
            )
            record = {
                "openalex_id": identifier,
                "status": "parsed",
                "xml": xml is not None,
                "pdf": pdf is not None,
                "primary": route["primary"],
                "review_required": route["review_required"],
                "input_errors": input_errors,
                "input_sha256": input_checksums,
                "elapsed_seconds": elapsed,
                "output": str(destination.relative_to(vault)),
                "route": diagnostics["route"],
                "sources": diagnostics["sources"],
                "validation": diagnostics["validation"],
            }
            print(f"[{index:03d}/{len(identifiers):03d}] {identifier} primary={route['primary']} review={route['review_required']} {elapsed:.2f}s")
        except Exception as error:
            failures += 1
            record = {
                "openalex_id": identifier,
                "status": "failed",
                "input_errors": input_errors,
                "error": f"{type(error).__name__}: {error}",
            }
            print(f"[{index:03d}/{len(identifiers):03d}] {identifier} FAILED: {error}", file=sys.stderr)
        results.append(record)
        state_works[identifier] = record
        atomic_json(
            state_path,
            {
                "schema_version": 1,
                "created_at": prior_state.get("created_at") if isinstance(prior_state, dict) else utc_now(),
                "updated_at": utc_now(),
                "configuration": {"strategy": "xml-first-docling-fallback"},
                "works": state_works,
            },
        )
    parsed = [item for item in results if item["status"] == "parsed"]
    times = [float(item["elapsed_seconds"]) for item in parsed]
    summary = {
        "requested": len(identifiers),
        "parsed": len(parsed),
        "failed": failures,
        "xml_parsed": sum(bool(item.get("xml")) for item in parsed),
        "pdf_parsed": sum(bool(item.get("pdf")) for item in parsed),
        "reviews": sum(bool(item.get("review_required")) for item in parsed),
        "elapsed_seconds": {"total": sum(times), "mean": statistics.fmean(times) if times else 0.0, "median": statistics.median(times) if times else 0.0},
    }
    atomic_json(vault / "state" / "parsing-summary.json", summary)
    print(json.dumps(summary, indent=2))
    if failures:
        raise ParseError(f"{failures} work(s) failed; inspect state/parsing.json and rerun.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse research-vault XML and PDF sources.")
    parser.add_argument("vault", type=Path)
    parser.add_argument("--force", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        command_parse(args)
    except (ParseError, OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
