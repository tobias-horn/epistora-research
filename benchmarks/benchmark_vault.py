#!/usr/bin/env python3
"""Report mechanical vault quality and shortlist-balance metrics.

The metrics in this script are structural proxies. They deliberately do not
claim to measure factual truth, citation entailment, or literature recall.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import re
import statistics


WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
SOURCE_CLAIM_LINK = re.compile(r"\[\[([^\]]+)#\^c[\w-]+(?:\|[^\]]+)?\]\]", re.I)
CLAIM_HEADING = re.compile(r"^###\s+C\d+\b", re.M)
PROPOSITION_HEADING = re.compile(r"^###\s+P\d+\b", re.M)
STABLE_CLAIM_ID = re.compile(r"\^c[\w-]+\b", re.I)
STABLE_PROPOSITION_ID = re.compile(r"\^p[\w-]+\b", re.I)
TYPED_CONNECTION = re.compile(r"^-\s+\*\*[^*]+\*\*\s*(?:→|->|:)\s*\[\[", re.M)


def normalize_term(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def parse_scalar(raw: str) -> object:
    value = raw.strip()
    if not value:
        return ""
    if value in {"[]", "{}"}:
        return [] if value == "[]" else {}
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip("\"'") for part in inner.split(",")]
    if value.casefold() in {"true", "false"}:
        return value.casefold() == "true"
    return value.strip("\"'")


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text
    closing = text.find("\n---", 4)
    if closing < 0:
        return {}, text
    raw = text[4:closing]
    body = text[closing + 4 :].lstrip("\n")
    result: dict[str, object] = {}
    current_list: str | None = None
    for line in raw.splitlines():
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item and current_list:
            values = result.setdefault(current_list, [])
            if isinstance(values, list):
                values.append(item.group(1).strip().strip("\"'"))
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            current_list = None
            continue
        key, value = match.groups()
        if value == "":
            result[key] = []
            current_list = key
        else:
            result[key] = parse_scalar(value)
            current_list = None
    return result, body


def note_records(vault: Path) -> list[dict[str, object]]:
    records = []
    for folder in ("sources", "wiki"):
        directory = vault / folder
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            frontmatter, body = parse_frontmatter(text)
            records.append(
                {
                    "path": path,
                    "relative": str(path.relative_to(vault)),
                    "folder": folder,
                    "frontmatter": frontmatter,
                    "body": body,
                    "links": WIKILINK.findall(body),
                }
            )
    return records


def list_values(frontmatter: dict[str, object], key: str) -> list[str]:
    value = frontmatter.get(key)
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)] if value else []


def link_target(raw: str) -> str:
    value = raw.split("|", 1)[0].split("#", 1)[0].strip()
    if value.casefold().endswith(".md"):
        value = value[:-3]
    return Path(value).name


def frontmatter_link_targets(frontmatter: dict[str, object], key: str) -> set[str]:
    targets = set()
    for value in list_values(frontmatter, key):
        match = WIKILINK.search(value)
        targets.add(normalize_term(link_target(match.group(1) if match else value)))
    return {target for target in targets if target}


def split_heading_blocks(pattern: re.Pattern[str], body: str) -> list[str]:
    matches = list(pattern.finditer(body))
    blocks = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        blocks.append(body[match.start() : end])
    return blocks


def audit_vault(vault: Path) -> dict[str, object]:
    records = note_records(vault)
    source_records = [record for record in records if record["folder"] == "sources"]
    wiki_records = [record for record in records if record["folder"] == "wiki"]

    identity_map: dict[str, set[str]] = defaultdict(set)
    for record in records:
        path = record["path"]
        frontmatter = record["frontmatter"]
        assert isinstance(path, Path) and isinstance(frontmatter, dict)
        identities = [path.stem, frontmatter.get("title")]
        identities.extend(list_values(frontmatter, "aliases"))
        for identity in identities:
            term = normalize_term(identity)
            if term:
                identity_map[term].add(str(record["relative"]))

    broken_links = []
    inbound: Counter[str] = Counter()
    for record in records:
        links = record["links"]
        assert isinstance(links, list)
        for raw_link in links:
            target = normalize_term(link_target(str(raw_link)))
            matches = identity_map.get(target, set())
            if not matches:
                broken_links.append({"from": record["relative"], "target": raw_link})
            else:
                for matched in matches:
                    if matched != record["relative"]:
                        inbound[matched] += 1

    duplicate_identities = {
        term: sorted(paths) for term, paths in identity_map.items() if len(paths) > 1
    }
    orphan_wiki_pages = sorted(
        str(record["relative"])
        for record in wiki_records
        if inbound[str(record["relative"])] == 0
    )

    claim_count = claim_ids = claims_with_locator = 0
    for record in source_records:
        body = str(record["body"])
        blocks = split_heading_blocks(CLAIM_HEADING, body)
        claim_count += len(blocks)
        claim_ids += sum(bool(STABLE_CLAIM_ID.search(block)) for block in blocks)
        claims_with_locator += sum(
            bool(re.search(r"^-\s+\*\*Locator:\*\*\s*\S.+$", block, re.M))
            for block in blocks
        )

    proposition_count = proposition_ids = propositions_with_claim_citations = 0
    wiki_without_body_sources = []
    source_property_drift = []
    typed_connections = connection_lines = 0
    for record in wiki_records:
        body = str(record["body"])
        frontmatter = record["frontmatter"]
        assert isinstance(frontmatter, dict)
        blocks = split_heading_blocks(PROPOSITION_HEADING, body)
        proposition_count += len(blocks)
        proposition_ids += sum(bool(STABLE_PROPOSITION_ID.search(block)) for block in blocks)
        propositions_with_claim_citations += sum(
            bool(SOURCE_CLAIM_LINK.search(block)) for block in blocks
        )
        body_source_targets = {
            normalize_term(link_target(match.group(1)))
            for match in SOURCE_CLAIM_LINK.finditer(body)
        }
        if not body_source_targets:
            wiki_without_body_sources.append(str(record["relative"]))
        property_targets = frontmatter_link_targets(frontmatter, "sources")
        if property_targets != body_source_targets:
            source_property_drift.append(
                {
                    "page": record["relative"],
                    "property_only": sorted(property_targets - body_source_targets),
                    "body_only": sorted(body_source_targets - property_targets),
                }
            )
        connection_section = re.search(
            r"^##\s+Connections\s*$([\s\S]*?)(?=^##\s|\Z)", body, re.M
        )
        if connection_section:
            lines = [
                line for line in connection_section.group(1).splitlines() if line.lstrip().startswith("-")
            ]
            connection_lines += len(lines)
            typed_connections += sum(bool(TYPED_CONNECTION.match(line)) for line in lines)

    return {
        "notes": len(records),
        "source_notes": len(source_records),
        "wiki_pages": len(wiki_records),
        "broken_wikilinks": broken_links,
        "broken_wikilink_count": len(broken_links),
        "duplicate_identities": duplicate_identities,
        "duplicate_identity_count": len(duplicate_identities),
        "orphan_wiki_pages": orphan_wiki_pages,
        "orphan_wiki_page_count": len(orphan_wiki_pages),
        "source_claims": claim_count,
        "source_claims_with_stable_id": claim_ids,
        "source_claims_with_locator": claims_with_locator,
        "wiki_propositions": proposition_count,
        "wiki_propositions_with_stable_id": proposition_ids,
        "wiki_propositions_with_source_claim_citation": propositions_with_claim_citations,
        "wiki_pages_without_source_claim_links": wiki_without_body_sources,
        "source_property_drift": source_property_drift,
        "typed_connections": typed_connections,
        "connection_lines": connection_lines,
        "typed_connection_ratio": (
            typed_connections / connection_lines if connection_lines else None
        ),
    }


def normalized_entropy(counter: Counter[str]) -> float | None:
    total = sum(counter.values())
    if total == 0 or len(counter) < 2:
        return None
    entropy = -sum(
        (count / total) * math.log(count / total) for count in counter.values()
    )
    return entropy / math.log(len(counter))


def hhi(counter: Counter[str]) -> float | None:
    total = sum(counter.values())
    if total == 0:
        return None
    return sum((count / total) ** 2 for count in counter.values())


def summarize_counter(counter: Counter[str]) -> dict[str, object]:
    total = sum(counter.values())
    return {
        "counts": dict(counter.most_common()),
        "normalized_entropy": normalized_entropy(counter),
        "hhi": hhi(counter),
        "maximum_share": max(counter.values()) / total if total else None,
    }


def work_list(path: Path) -> list[dict[str, object]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"Expected a JSON array of objects: {path}")
    return value


def year_summary(years: list[int]) -> dict[str, object]:
    if not years:
        return {"count": 0}
    ordered = sorted(years)
    current = date.today().year
    return {
        "count": len(years),
        "minimum": ordered[0],
        "median": statistics.median(ordered),
        "maximum": ordered[-1],
        "last_5_years_share": sum(year >= current - 4 for year in years) / len(years),
        "last_10_years_share": sum(year >= current - 9 for year in years) / len(years),
    }


def audit_shortlist(path: Path) -> dict[str, object]:
    works = work_list(path)
    roles: Counter[str] = Counter()
    work_types: Counter[str] = Counter()
    languages: Counter[str] = Counter()
    primary_topics: Counter[str] = Counter()
    authors: Counter[str] = Counter()
    institutions: Counter[str] = Counter()
    availability: Counter[str] = Counter()
    discoveries: Counter[str] = Counter()
    years: list[int] = []
    citations: list[int] = []

    for work in works:
        roles.update(str(value) for value in work.get("roles") or [])
        work_types[str(work.get("type") or "unknown")] += 1
        languages[str(work.get("language") or "unknown")] += 1
        topic = work.get("primary_topic")
        if isinstance(topic, dict) and topic.get("name"):
            primary_topics[str(topic["name"])] += 1
        year = work.get("publication_year")
        if isinstance(year, int):
            years.append(year)
        cited = work.get("cited_by_count")
        if isinstance(cited, (int, float)):
            citations.append(int(cited))
        for author in work.get("authors") or []:
            if not isinstance(author, dict):
                continue
            author_id = author.get("id") or author.get("name")
            if author_id:
                authors[str(author_id)] += 1
            for institution in author.get("institutions") or []:
                if isinstance(institution, dict):
                    institution_id = institution.get("id") or institution.get("name")
                    if institution_id:
                        institutions[str(institution_id)] += 1
        lanes = set(str(value) for value in work.get("availability") or [])
        availability.update(lanes)
        if work.get("has_pdf"):
            availability["any-pdf"] += 1
        if work.get("has_xml"):
            availability["any-xml"] += 1
        if work.get("has_pdf") and work.get("has_xml"):
            availability["pdf-and-xml"] += 1
        discoveries.update(str(value) for value in work.get("discovered_by") or [])

    return {
        "works": len(works),
        "years": year_summary(years),
        "citations": {
            "count": len(citations),
            "median": statistics.median(citations) if citations else None,
            "maximum": max(citations) if citations else None,
        },
        "roles": summarize_counter(roles),
        "work_types": summarize_counter(work_types),
        "languages": summarize_counter(languages),
        "primary_topics": summarize_counter(primary_topics),
        "authors": summarize_counter(authors),
        "institutions": summarize_counter(institutions),
        "availability": dict(availability.most_common()),
        "discovery_searches": summarize_counter(discoveries),
    }


def audit_search_log(path: Path) -> dict[str, object]:
    events = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        value = json.loads(raw_line)
        if not isinstance(value, dict):
            raise ValueError(f"Expected a JSON object at {path}:{line_number}")
        if value.get("event") in {"search", "anchor-expansion"}:
            events.append(value)

    returned: dict[str, set[str]] = {}
    rows = []
    cumulative: set[str] = set()
    for event in events:
        search_id = str(event.get("search_id") or f"event-{len(rows) + 1}")
        identifiers = {
            str(value) for value in event.get("returned_ids") or [] if value
        }
        returned[search_id] = identifiers
        new_to_sequence = identifiers - cumulative
        cumulative.update(identifiers)
        rows.append(
            {
                "search_id": search_id,
                "stage": event.get("stage"),
                "strand": event.get("strand"),
                "returned": len(identifiers),
                "new_to_sequence": len(new_to_sequence),
                "sequence_novelty_ratio": (
                    len(new_to_sequence) / len(identifiers) if identifiers else None
                ),
                "logged_new_candidate_records": event.get("new_candidate_records"),
                "logged_new_version_groups": event.get("new_version_groups"),
                "elapsed_ms": event.get("elapsed_ms"),
            }
        )

    pairwise = []
    identifiers = list(returned)
    for left_index, left in enumerate(identifiers):
        for right in identifiers[left_index + 1 :]:
            union = returned[left] | returned[right]
            pairwise.append(
                {
                    "left": left,
                    "right": right,
                    "jaccard": len(returned[left] & returned[right]) / len(union)
                    if union
                    else None,
                }
            )
    jaccards = [
        float(item["jaccard"])
        for item in pairwise
        if item["jaccard"] is not None
    ]
    return {
        "events": rows,
        "event_count": len(rows),
        "cumulative_unique_records": len(cumulative),
        "pairwise_overlap": pairwise,
        "mean_pairwise_jaccard": statistics.mean(jaccards) if jaccards else None,
        "maximum_pairwise_jaccard": max(jaccards) if jaccards else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", type=Path)
    parser.add_argument("--shortlist", type=Path)
    parser.add_argument("--search-log", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.vault and not args.shortlist and not args.search_log:
        raise SystemExit("Provide --vault, --shortlist, --search-log, or a combination.")
    result: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Structural metrics do not measure factual truth or citation entailment.",
            "Shortlist balance does not measure relevance or absolute literature recall.",
        ],
    }
    if args.vault:
        vault = args.vault.expanduser().resolve()
        result["vault"] = str(vault)
        result["structural"] = audit_vault(vault)
    if args.shortlist:
        shortlist = args.shortlist.expanduser().resolve()
        result["shortlist"] = str(shortlist)
        result["source_selection"] = audit_shortlist(shortlist)
    if args.search_log:
        search_log = args.search_log.expanduser().resolve()
        result["search_log"] = str(search_log)
        result["retrieval"] = audit_search_log(search_log)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
