#!/usr/bin/env python3
"""Validate evidence links and build a derived claim index for a research vault."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile


FRONTMATTER_KEY = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
LIST_ITEM = re.compile(r"^\s+-\s+(.*)$")
SOURCE_HEADING = re.compile(r"^###\s+(C\d+)\s*[—-]\s*(.+?)\s*$", re.M)
PROPOSITION_HEADING = re.compile(r"^###\s+(P\d+)\s*[—-]\s*(.+?)\s*$", re.M)
BLOCK_ID = re.compile(r"\^([A-Za-z0-9-]+)\b")
FIELD = re.compile(r"^-\s+\*\*([^*]+):\*\*\s*(.*)$", re.M)
WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
CLAIM_LINK = re.compile(
    r"\[\[([^\]#|]+)#\^([A-Za-z0-9-]+)(?:\|([^\]]+))?\]\]"
)
CONNECTION = re.compile(
    r"^-\s+\*\*([a-z][a-z-]+)\*\*\s*(?:→|->)\s*"
    r"\[\[([^\]]+)\]\]\s*(?:[—-]\s*(.+))?$",
    re.M | re.I,
)

ALLOWED_RELATIONS = {
    "broader-than",
    "narrower-than",
    "part-of",
    "causes",
    "mediates",
    "moderates",
    "supports",
    "challenges",
    "operationalized-by",
    "measured-by",
    "applied-in",
    "distinguished-from",
    "prerequisite-for",
    "informs",
}
EVIDENCE_FIELDS = {"supports", "challenges", "qualifies", "illustrated-by"}


class IndexErrorReport(RuntimeError):
    """Raised when the vault cannot be inspected safely."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_scalar(raw: str) -> object:
    value = raw.strip()
    if not value:
        return ""
    if value == "[]":
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",")]
    if value.casefold() in {"true", "false"}:
        return value.casefold() == "true"
    return value.strip("\"'")


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    properties: dict[str, object] = {}
    current_list: str | None = None
    for line in text[4:end].splitlines():
        item = LIST_ITEM.match(line)
        if item and current_list:
            values = properties.setdefault(current_list, [])
            if isinstance(values, list):
                values.append(item.group(1).strip().strip("\"'"))
            continue
        match = FRONTMATTER_KEY.match(line)
        if not match:
            current_list = None
            continue
        key, value = match.groups()
        if value == "":
            properties[key] = []
            current_list = key
        else:
            properties[key] = parse_scalar(value)
            current_list = None
    return properties, text[end + 4 :].lstrip("\n")


def list_values(properties: dict[str, object], key: str) -> list[str]:
    value = properties.get(key)
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)] if value else []


def split_blocks(pattern: re.Pattern[str], body: str) -> list[tuple[re.Match[str], str]]:
    matches = list(pattern.finditer(body))
    return [
        (match, body[match.start() : matches[index + 1].start() if index + 1 < len(matches) else len(body)])
        for index, match in enumerate(matches)
    ]


def fields(block: str) -> dict[str, str]:
    return {
        match.group(1).strip().casefold(): match.group(2).strip()
        for match in FIELD.finditer(block)
    }


def normalized_target(raw: str) -> str:
    target = raw.split("|", 1)[0].split("#", 1)[0].strip()
    if target.casefold().endswith(".md"):
        target = target[:-3]
    return Path(target).name.casefold()


def markdown_records(vault: Path) -> list[dict[str, object]]:
    records = []
    for folder in ("sources", "wiki"):
        directory = vault / folder
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            properties, body = parse_frontmatter(text)
            records.append(
                {
                    "path": path,
                    "relative": str(path.relative_to(vault)),
                    "folder": folder,
                    "properties": properties,
                    "body": body,
                }
            )
    return records


def required_property(
    record: dict[str, object], key: str, errors: list[dict[str, str]]
) -> str:
    properties = record["properties"]
    assert isinstance(properties, dict)
    value = properties.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(
            {
                "code": "missing-property",
                "page": str(record["relative"]),
                "detail": key,
            }
        )
        return ""
    return value.strip()


def inspect_vault(vault: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    records = markdown_records(vault)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    index: list[dict[str, object]] = []
    identity: dict[str, str] = {}
    claim_ids: dict[str, str] = {}
    proposition_ids: dict[str, str] = {}
    work_ids: dict[str, str] = {}
    wiki_ids: dict[str, str] = {}

    for record in records:
        properties = record["properties"]
        path = record["path"]
        assert isinstance(properties, dict) and isinstance(path, Path)
        names = [path.stem, str(properties.get("title") or "")]
        names.extend(list_values(properties, "aliases"))
        for name in names:
            normalized = name.strip().casefold()
            if normalized:
                existing = identity.get(normalized)
                if existing and existing != str(record["relative"]):
                    errors.append(
                        {
                            "code": "identity-collision",
                            "page": str(record["relative"]),
                            "detail": f"{name} already identifies {existing}",
                        }
                    )
                else:
                    identity[normalized] = str(record["relative"])

    for record in records:
        properties = record["properties"]
        body = str(record["body"])
        assert isinstance(properties, dict)
        if record["folder"] == "sources":
            required_property(record, "title", errors)
            work_id = required_property(record, "openalex_id", errors)
            if work_id:
                existing = work_ids.get(work_id.casefold())
                if existing and existing != str(record["relative"]):
                    errors.append(
                        {
                            "code": "duplicate-work-id",
                            "page": str(record["relative"]),
                            "detail": f"{work_id} already identifies {existing}",
                        }
                    )
                else:
                    work_ids[work_id.casefold()] = str(record["relative"])
            source_blocks = split_blocks(SOURCE_HEADING, body)
            if not source_blocks:
                warnings.append(
                    {
                        "code": "source-without-claims",
                        "page": str(record["relative"]),
                        "detail": "No C-numbered claim blocks",
                    }
                )
            for match, block in source_blocks:
                values = fields(block)
                identifier_match = BLOCK_ID.search(values.get("claim", ""))
                if not identifier_match:
                    errors.append(
                        {
                            "code": "missing-claim-id",
                            "page": str(record["relative"]),
                            "detail": match.group(1),
                        }
                    )
                    continue
                identifier = identifier_match.group(1)
                if identifier in claim_ids:
                    errors.append(
                        {
                            "code": "duplicate-id",
                            "page": str(record["relative"]),
                            "detail": identifier,
                        }
                    )
                claim_ids[identifier] = str(record["relative"])
                if not values.get("locator"):
                    errors.append(
                        {
                            "code": "missing-locator",
                            "page": str(record["relative"]),
                            "detail": identifier,
                        }
                    )
                claim_text = BLOCK_ID.sub("", values.get("claim", "")).strip()
                index.append(
                    {
                        "record_type": "source-claim",
                        "id": identifier,
                        "page": record["relative"],
                        "title": properties.get("title") or "",
                        "study_id": properties.get("study_id") or None,
                        "concepts": list_values(properties, "concepts"),
                        "facets": list_values(properties, "facets"),
                        "claim": claim_text,
                        "scope": values.get("scope and conditions", ""),
                        "locator": values.get("locator", ""),
                        "evidence_type": values.get("evidence type", ""),
                    }
                )
        else:
            required_property(record, "title", errors)
            wiki_id = required_property(record, "wiki_id", errors)
            if wiki_id:
                existing = wiki_ids.get(wiki_id.casefold())
                if existing and existing != str(record["relative"]):
                    errors.append(
                        {
                            "code": "duplicate-wiki-id",
                            "page": str(record["relative"]),
                            "detail": f"{wiki_id} already identifies {existing}",
                        }
                    )
                else:
                    wiki_ids[wiki_id.casefold()] = str(record["relative"])
            proposition_blocks = split_blocks(PROPOSITION_HEADING, body)
            if not proposition_blocks:
                warnings.append(
                    {
                        "code": "wiki-without-propositions",
                        "page": str(record["relative"]),
                        "detail": "No P-numbered proposition blocks",
                    }
                )
            cited_pages: set[str] = set()
            for match, block in proposition_blocks:
                values = fields(block)
                identifier_match = BLOCK_ID.search(values.get("statement", ""))
                if not identifier_match:
                    errors.append(
                        {
                            "code": "missing-proposition-id",
                            "page": str(record["relative"]),
                            "detail": match.group(1),
                        }
                    )
                    continue
                identifier = identifier_match.group(1)
                if identifier in proposition_ids:
                    errors.append(
                        {
                            "code": "duplicate-id",
                            "page": str(record["relative"]),
                            "detail": identifier,
                        }
                    )
                proposition_ids[identifier] = str(record["relative"])
                evidence = []
                for field_name in EVIDENCE_FIELDS:
                    for citation in CLAIM_LINK.finditer(values.get(field_name, "")):
                        target, claim_id, _display = citation.groups()
                        normalized_page = normalized_target(target)
                        cited_pages.add(identity.get(normalized_page, normalized_page))
                        evidence.append(
                            {
                                "role": field_name,
                                "page": target.strip(),
                                "claim_id": claim_id,
                            }
                        )
                if not evidence:
                    errors.append(
                        {
                            "code": "proposition-without-evidence",
                            "page": str(record["relative"]),
                            "detail": identifier,
                        }
                    )
                statement = BLOCK_ID.sub("", values.get("statement", "")).strip()
                index.append(
                    {
                        "record_type": "wiki-proposition",
                        "id": identifier,
                        "page": record["relative"],
                        "wiki_id": wiki_id,
                        "title": properties.get("title") or "",
                        "aliases": list_values(properties, "aliases"),
                        "facets": list_values(properties, "facets"),
                        "kind": properties.get("kind") or "",
                        "statement": statement,
                        "evidence_pattern": values.get("evidence pattern", ""),
                        "assessment": values.get("assessment", ""),
                        "scope": values.get("scope", ""),
                        "evidence": evidence,
                    }
                )
            property_sources = {
                identity.get(
                    normalized_target(match.group(1) if match else value),
                    normalized_target(match.group(1) if match else value),
                )
                for value in list_values(properties, "sources")
                for match in [WIKILINK.search(value)]
            }
            if property_sources != cited_pages:
                errors.append(
                    {
                        "code": "source-property-drift",
                        "page": str(record["relative"]),
                        "detail": json.dumps(
                            {
                                "property_only": sorted(property_sources - cited_pages),
                                "body_only": sorted(cited_pages - property_sources),
                            },
                            ensure_ascii=False,
                        ),
                    }
                )

            connection_section = re.search(
                r"^##\s+Connections\s*$([\s\S]*?)(?=^##\s|\Z)", body, re.M
            )
            if connection_section:
                for match in CONNECTION.finditer(connection_section.group(1)):
                    relation = match.group(1).casefold()
                    target = match.group(2).strip()
                    rationale = (match.group(3) or "").strip()
                    if relation not in ALLOWED_RELATIONS:
                        errors.append(
                            {
                                "code": "unknown-relation",
                                "page": str(record["relative"]),
                                "detail": relation,
                            }
                        )
                    if normalized_target(target) not in identity:
                        errors.append(
                            {
                                "code": "missing-relation-target",
                                "page": str(record["relative"]),
                                "detail": target,
                            }
                        )
                    index.append(
                        {
                            "record_type": "wiki-relation",
                            "from_wiki_id": wiki_id,
                            "from_page": record["relative"],
                            "relation": relation,
                            "to": target,
                            "rationale": rationale,
                        }
                    )

    for entry in index:
        if entry.get("record_type") != "wiki-proposition":
            continue
        for citation in entry.get("evidence") or []:
            assert isinstance(citation, dict)
            claim_id = str(citation.get("claim_id") or "")
            target = normalized_target(str(citation.get("page") or ""))
            resolved_target = identity.get(target)
            if claim_id not in claim_ids:
                errors.append(
                    {
                        "code": "missing-cited-claim",
                        "page": str(entry.get("page")),
                        "detail": claim_id,
                    }
                )
            elif resolved_target != claim_ids[claim_id]:
                errors.append(
                    {
                        "code": "claim-target-mismatch",
                        "page": str(entry.get("page")),
                        "detail": f"{target}#{claim_id}",
                    }
                )

    summary = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "source_notes": sum(record["folder"] == "sources" for record in records),
        "wiki_pages": sum(record["folder"] == "wiki" for record in records),
        "source_claims": sum(item["record_type"] == "source-claim" for item in index),
        "wiki_propositions": sum(
            item["record_type"] == "wiki-proposition" for item in index
        ),
        "wiki_relations": sum(item["record_type"] == "wiki-relation" for item in index),
        "errors": errors,
        "warnings": warnings,
    }
    return index, summary


def atomic_write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate source-claim/wiki-proposition links and build a derived JSONL index."
    )
    parser.add_argument("vault", type=Path)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate without writing state/wiki-index.jsonl.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    vault = Path(os.path.abspath(args.vault.expanduser()))
    if not vault.is_dir():
        print(f"Error: vault does not exist: {vault}", file=sys.stderr)
        return 2
    index, summary = inspect_vault(vault)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["errors"]:
        return 1
    if not args.check:
        output = args.output or vault / "state" / "wiki-index.jsonl"
        if not output.is_absolute():
            output = vault / output
        atomic_write_jsonl(output, index)
        print(f"Wrote {len(index)} records to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
