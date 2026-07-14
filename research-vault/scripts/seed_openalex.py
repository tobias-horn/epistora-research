#!/usr/bin/env python3
"""Build and finalize a logged OpenAlex candidate set for a research vault."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://api.openalex.org"
DEFAULT_FILTER = (
    "type:article|book|book-chapter|preprint|report|review|dissertation,"
    "is_retracted:false"
)
LABELS = {"unreviewed", "core", "supporting", "contextual", "exclude", "uncertain"}
TYPE_PRIORITY = {
    "article": 8,
    "review": 8,
    "book": 7,
    "book-chapter": 6,
    "report": 5,
    "dissertation": 4,
    "preprint": 3,
}


class SeedingError(RuntimeError):
    """Raised when seeding state or an OpenAlex operation is invalid."""


def positive_count(raw: str) -> int:
    value = int(raw)
    if not 1 <= value <= 100:
        raise argparse.ArgumentTypeError("must be between 1 and 100")
    return value


def optional_count(raw: str) -> int:
    value = int(raw)
    if not 0 <= value <= 100:
        raise argparse.ArgumentTypeError("must be between 0 and 100")
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SeedingError(f"Required state file is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise SeedingError(f"Invalid JSON in {path}: {error}") from error


def append_log(path: Path, entry: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
        handle.write("\n")


def normalize_vault(raw: Path) -> Path:
    vault = Path(os.path.abspath(raw.expanduser()))
    required = (
        vault / "state" / "research.md",
        vault / "state" / "candidates.json",
        vault / "state" / "queue.json",
    )
    if not vault.is_dir() or any(not path.is_file() for path in required):
        raise SeedingError(f"Not an initialized research vault: {vault}")
    return vault


def load_state(vault: Path) -> dict[str, object]:
    value = load_json(vault / "state" / "candidates.json")
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise SeedingError("state/candidates.json has an unsupported schema.")
    if not isinstance(value.get("works"), dict):
        raise SeedingError("state/candidates.json must contain a works object.")
    return value


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def resolve_api_key(vault: Path, env_file: Path | None) -> str:
    if env_file is not None:
        load_env_file(Path(os.path.abspath(env_file.expanduser())))
    else:
        for candidate in (Path.cwd() / ".env", vault / ".env", vault.parent / ".env"):
            load_env_file(candidate)
    key = os.environ.get("OPEN_ALEX") or os.environ.get("OPENALEX_API_KEY")
    if not key:
        raise SeedingError(
            "OpenAlex API key not found. Set OPEN_ALEX or OPENALEX_API_KEY, "
            "or pass --env-file."
        )
    return key


def request_json(endpoint: str, params: dict[str, object], api_key: str) -> dict[str, object]:
    safe_params = {key: value for key, value in params.items() if value is not None}
    url = f"{API_ROOT}/{endpoint.lstrip('/')}?" + urlencode(
        {**safe_params, "api_key": api_key}
    )
    request = Request(url, headers={"User-Agent": "research-vault/0.1"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise SeedingError("OpenAlex returned a non-object response.")
            return payload
        except HTTPError as error:
            last_error = error
            if error.code not in {429, 500, 502, 503, 504}:
                break
        except (URLError, TimeoutError) as error:
            last_error = error
        if attempt < 2:
            time.sleep(2**attempt)
    raise SeedingError(f"OpenAlex request failed after retries: {last_error}")


def reconstruct_abstract(index: object) -> str | None:
    if not isinstance(index, dict) or not index:
        return None
    positioned: list[tuple[int, str]] = []
    for word, positions in index.items():
        if isinstance(word, str) and isinstance(positions, list):
            positioned.extend((position, word) for position in positions if isinstance(position, int))
    return " ".join(word for _, word in sorted(positioned)) or None


def location_summary(location: object) -> dict[str, object] | None:
    if not isinstance(location, dict):
        return None
    source = location.get("source") if isinstance(location.get("source"), dict) else {}
    return {
        "landing_page_url": location.get("landing_page_url"),
        "pdf_url": location.get("pdf_url"),
        "is_oa": location.get("is_oa"),
        "version": location.get("version"),
        "license": location.get("license"),
        "source": {
            "id": source.get("id"),
            "name": source.get("display_name"),
            "type": source.get("type"),
        },
    }


def compact_work(work: dict[str, object]) -> dict[str, object]:
    authors = []
    for authorship in work.get("authorships") or []:
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author") if isinstance(authorship.get("author"), dict) else {}
        institutions = []
        for institution in authorship.get("institutions") or []:
            if isinstance(institution, dict):
                institutions.append(
                    {"id": institution.get("id"), "name": institution.get("display_name")}
                )
        authors.append(
            {
                "id": author.get("id"),
                "name": author.get("display_name"),
                "orcid": author.get("orcid"),
                "institutions": institutions,
            }
        )
    topics = [
        {"id": topic.get("id"), "name": topic.get("display_name"), "score": topic.get("score")}
        for topic in work.get("topics") or []
        if isinstance(topic, dict)
    ]
    keywords = [
        {"id": keyword.get("id"), "name": keyword.get("display_name"), "score": keyword.get("score")}
        for keyword in work.get("keywords") or []
        if isinstance(keyword, dict)
    ]
    primary_topic = work.get("primary_topic") if isinstance(work.get("primary_topic"), dict) else {}
    content = work.get("has_content") if isinstance(work.get("has_content"), dict) else {}
    best_location = location_summary(work.get("best_oa_location"))
    return {
        "openalex_id": work.get("id"),
        "doi": work.get("doi"),
        "title": work.get("display_name") or work.get("title"),
        "publication_year": work.get("publication_year"),
        "publication_date": work.get("publication_date"),
        "type": work.get("type"),
        "language": work.get("language"),
        "authors": authors,
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "cited_by_count": work.get("cited_by_count") or 0,
        "primary_topic": {
            "id": primary_topic.get("id"),
            "name": primary_topic.get("display_name"),
        }
        if primary_topic
        else None,
        "topics": topics,
        "keywords": keywords,
        "is_oa": bool((work.get("open_access") or {}).get("is_oa"))
        if isinstance(work.get("open_access"), dict)
        else False,
        "has_pdf": bool(content.get("pdf") or (best_location or {}).get("pdf_url")),
        "primary_location": location_summary(work.get("primary_location")),
        "best_oa_location": best_location,
        "referenced_works": work.get("referenced_works") or [],
        "related_works": work.get("related_works") or [],
    }


def normalize_openalex_id(raw: str) -> str:
    identifier = raw.strip().rstrip("/").rsplit("/", 1)[-1].upper()
    if not re.fullmatch(r"W\d+", identifier):
        raise SeedingError(f"Invalid OpenAlex work ID: {raw}")
    return f"https://openalex.org/{identifier}"


def normalized_title(title: object) -> str:
    text = unicodedata.normalize("NFKD", str(title or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def version_key(metadata: dict[str, object]) -> str:
    title = normalized_title(metadata.get("title"))
    if title:
        return "title:" + hashlib.sha1(title.encode("utf-8")).hexdigest()[:20]
    doi = str(metadata.get("doi") or "").lower()
    if doi:
        return "doi:" + doi
    return "openalex:" + str(metadata.get("openalex_id"))


def make_search_id(stage: str, seed: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = re.sub(r"[^a-z0-9]+", "-", stage.lower()).strip("-")[:24]
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"{stamp}-{slug}-{digest}"


def merge_work(
    state: dict[str, object],
    raw_work: dict[str, object],
    discovery: dict[str, object],
) -> str:
    metadata = compact_work(raw_work)
    identifier = metadata.get("openalex_id")
    if not isinstance(identifier, str):
        raise SeedingError("OpenAlex work is missing an ID.")
    works = state["works"]
    assert isinstance(works, dict)
    existing = works.get(identifier)
    if not isinstance(existing, dict):
        existing = {
            "metadata": metadata,
            "version_key": version_key(metadata),
            "discovered_by": [],
            "screening": {
                "label": "unreviewed",
                "roles": [],
                "reason": "",
                "terms": [],
                "updated_at": None,
            },
            "selected": False,
        }
        works[identifier] = existing
    else:
        existing["metadata"] = metadata
        existing["version_key"] = version_key(metadata)
    discoveries = existing.get("discovered_by")
    if not isinstance(discoveries, list):
        discoveries = []
        existing["discovered_by"] = discoveries
    if not any(item.get("search_id") == discovery.get("search_id") for item in discoveries):
        discoveries.append(discovery)
    return identifier


def build_filter(extra: str | None, from_year: int | None) -> str:
    parts = [DEFAULT_FILTER]
    if extra:
        parts.append(extra.strip().strip(","))
    if from_year:
        parts.append(f"from_publication_date:{from_year}-01-01")
    return ",".join(part for part in parts if part)


def raw_path(vault: Path, search_id: str) -> Path:
    return vault / "raw" / "openalex" / f"{search_id}.json"


def save_raw(vault: Path, search_id: str, request_data: object, response_data: object) -> Path:
    path = raw_path(vault, search_id)
    atomic_write_json(
        path,
        {
            "search_id": search_id,
            "saved_at": utc_now(),
            "request": request_data,
            "response": response_data,
        },
    )
    return path


def print_result_preview(results: list[dict[str, object]], limit: int = 10) -> None:
    for rank, work in enumerate(results[:limit], 1):
        print(
            f"{rank:>2}. {work.get('display_name') or work.get('title')} "
            f"({work.get('publication_year') or 'n.d.'}) [{work.get('type') or 'unknown'}]"
        )


def command_search(args: argparse.Namespace) -> None:
    vault = normalize_vault(args.vault)
    state = load_state(vault)
    works_before = state["works"]
    assert isinstance(works_before, dict)
    record_count_before = len(works_before)
    group_count_before = len(
        {str(candidate.get("version_key")) for candidate in works_before.values() if isinstance(candidate, dict)}
    )
    api_key = resolve_api_key(vault, args.env_file)
    search_filter = build_filter(args.filter, args.from_year)
    params: dict[str, object] = {
        "search": args.query,
        "filter": search_filter,
        "per_page": args.per_page,
    }
    if args.sort == "newest":
        params["sort"] = "publication_date:desc"
    elif args.sort == "cited":
        params["sort"] = "cited_by_count:desc"
    search_id = make_search_id(args.stage, args.query + args.strand + utc_now())
    started = time.perf_counter()
    payload = request_json("works", params, api_key)
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    results = payload.get("results")
    if not isinstance(results, list):
        raise SeedingError("OpenAlex search response is missing results.")
    identifiers = []
    for rank, raw_work in enumerate(results, 1):
        if not isinstance(raw_work, dict):
            continue
        identifiers.append(
            merge_work(
                state,
                raw_work,
                {
                    "search_id": search_id,
                    "stage": args.stage,
                    "strand": args.strand,
                    "rank": rank,
                },
            )
        )
    state["updated_at"] = utc_now()
    works_after = state["works"]
    assert isinstance(works_after, dict)
    group_count_after = len(
        {str(candidate.get("version_key")) for candidate in works_after.values() if isinstance(candidate, dict)}
    )
    new_records = len(works_after) - record_count_before
    new_groups = group_count_after - group_count_before
    atomic_write_json(vault / "state" / "candidates.json", state)
    request_data = {**params, "sort": params.get("sort", "relevance_score")}
    saved = save_raw(vault, search_id, request_data, payload)
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    append_log(
        vault / "state" / "search-log.jsonl",
        {
            "event": "search",
            "search_id": search_id,
            "stage": args.stage,
            "strand": args.strand,
            "rationale": args.rationale,
            "query": args.query,
            "filter": search_filter,
            "sort": request_data["sort"],
            "executed_at": utc_now(),
            "total_results": meta.get("count"),
            "returned_results": len(identifiers),
            "returned_ids": identifiers,
            "new_candidate_records": new_records,
            "new_version_groups": new_groups,
            "already_known_records": len(identifiers) - new_records,
            "elapsed_ms": elapsed_ms,
            "raw_file": str(saved.relative_to(vault)),
        },
    )
    print(f"Search ID: {search_id}")
    print(f"OpenAlex matches: {meta.get('count', 'unknown')}; returned: {len(identifiers)}")
    print(
        f"New records: {new_records}; new version groups: {new_groups}; "
        f"candidate total: {len(state['works'])}"
    )
    print(f"Raw response: {saved}")
    print_result_preview([item for item in results if isinstance(item, dict)])


def batch(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def command_expand_anchor(args: argparse.Namespace) -> None:
    vault = normalize_vault(args.vault)
    state = load_state(vault)
    works_before = state["works"]
    assert isinstance(works_before, dict)
    record_count_before = len(works_before)
    group_count_before = len(
        {str(candidate.get("version_key")) for candidate in works_before.values() if isinstance(candidate, dict)}
    )
    api_key = resolve_api_key(vault, args.env_file)
    anchor_url = normalize_openalex_id(args.id)
    anchor_short = anchor_url.rsplit("/", 1)[-1]
    anchor = request_json(f"works/{anchor_short}", {}, api_key)
    search_id = make_search_id("anchor", anchor_short + utc_now())
    raw_responses: dict[str, object] = {"anchor": anchor, "reference_batches": []}
    merged: list[str] = []
    if not args.no_references:
        reference_ids = [
            str(value).rsplit("/", 1)[-1]
            for value in anchor.get("referenced_works") or []
            if isinstance(value, str)
        ]
        for chunk_number, identifiers in enumerate(batch(reference_ids, 100), 1):
            params = {
                "filter": "openalex:" + "|".join(identifiers) + "," + DEFAULT_FILTER,
                "per_page": 100,
            }
            payload = request_json("works", params, api_key)
            raw_responses["reference_batches"].append(payload)  # type: ignore[union-attr]
            for rank, raw_work in enumerate(payload.get("results") or [], 1):
                if isinstance(raw_work, dict):
                    merged.append(
                        merge_work(
                            state,
                            raw_work,
                            {
                                "search_id": search_id,
                                "stage": "anchor-reference",
                                "strand": args.strand,
                                "rank": (chunk_number - 1) * 100 + rank,
                                "anchor_id": anchor_url,
                            },
                        )
                    )
    recent_ids: list[str] = []
    if args.recent_citing:
        recent_filter = build_filter(
            f"cites:{anchor_short}", args.from_year or datetime.now(timezone.utc).year - 2
        )
        params = {
            "filter": recent_filter,
            "sort": "publication_date:desc",
            "per_page": args.recent_citing,
        }
        recent = request_json("works", params, api_key)
        raw_responses["recent_citing"] = recent
        for rank, raw_work in enumerate(recent.get("results") or [], 1):
            if isinstance(raw_work, dict):
                recent_ids.append(
                    merge_work(
                        state,
                        raw_work,
                        {
                            "search_id": search_id,
                            "stage": "recent-citing",
                            "strand": args.strand,
                            "rank": rank,
                            "anchor_id": anchor_url,
                        },
                    )
                )
    if isinstance(anchor, dict):
        merge_work(
            state,
            anchor,
            {
                "search_id": search_id,
                "stage": "anchor",
                "strand": args.strand,
                "rank": 1,
            },
        )
    state["updated_at"] = utc_now()
    works_after = state["works"]
    assert isinstance(works_after, dict)
    group_count_after = len(
        {str(candidate.get("version_key")) for candidate in works_after.values() if isinstance(candidate, dict)}
    )
    atomic_write_json(vault / "state" / "candidates.json", state)
    saved = save_raw(
        vault,
        search_id,
        {
            "operation": "expand-anchor",
            "anchor_id": anchor_url,
            "references": not args.no_references,
            "recent_citing": args.recent_citing,
            "from_year": args.from_year,
        },
        raw_responses,
    )
    append_log(
        vault / "state" / "search-log.jsonl",
        {
            "event": "anchor-expansion",
            "search_id": search_id,
            "stage": "anchor-expansion",
            "strand": args.strand,
            "rationale": args.rationale,
            "anchor_id": anchor_url,
            "anchor_title": anchor.get("display_name"),
            "executed_at": utc_now(),
            "reference_records": len(set(merged)),
            "recent_citing_records": len(set(recent_ids)),
            "new_candidate_records": len(works_after) - record_count_before,
            "new_version_groups": group_count_after - group_count_before,
            "returned_ids": sorted(set(merged + recent_ids)),
            "raw_file": str(saved.relative_to(vault)),
        },
    )
    print(f"Expanded anchor: {anchor.get('display_name')} ({anchor_short})")
    print(f"References merged: {len(set(merged))}; recent citing merged: {len(set(recent_ids))}")
    print(f"Candidate total: {len(state['works'])}; raw response: {saved}")


def command_review(args: argparse.Namespace) -> None:
    vault = normalize_vault(args.vault)
    state = load_state(vault)
    works = state["works"]
    assert isinstance(works, dict)
    rows = []
    for identifier, candidate in works.items():
        if not isinstance(candidate, dict):
            continue
        screening = candidate.get("screening") if isinstance(candidate.get("screening"), dict) else {}
        if args.label != "any" and screening.get("label", "unreviewed") != args.label:
            continue
        discoveries = candidate.get("discovered_by") or []
        if args.search_id and not any(
            isinstance(item, dict) and item.get("search_id") == args.search_id
            for item in discoveries
        ):
            continue
        metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
        rows.append(
            {
                "openalex_id": identifier,
                "title": metadata.get("title"),
                "year": metadata.get("publication_year"),
                "type": metadata.get("type"),
                "cited_by_count": metadata.get("cited_by_count"),
                "authors": [item.get("name") for item in (metadata.get("authors") or [])[:8]],
                "abstract": metadata.get("abstract"),
                "primary_topic": (metadata.get("primary_topic") or {}).get("name")
                if isinstance(metadata.get("primary_topic"), dict)
                else None,
                "has_pdf": metadata.get("has_pdf"),
                "label": screening.get("label"),
                "roles": screening.get("roles") or [],
                "selected": candidate.get("selected", False),
                "discovered_by": discoveries,
            }
        )
    selected = rows[args.offset : args.offset + args.limit]
    if args.format == "json":
        print(json.dumps(selected, ensure_ascii=False, indent=2))
        return
    for index, row in enumerate(selected, args.offset + 1):
        print(f"## {index}. {row['title']} ({row['year'] or 'n.d.'})")
        print(f"- OpenAlex: {row['openalex_id']}")
        print(f"- Type: {row['type']}; citations: {row['cited_by_count']}; PDF: {row['has_pdf']}")
        print(f"- Authors: {', '.join(str(name) for name in row['authors'] if name)}")
        if row["abstract"]:
            abstract = str(row["abstract"])
            print(f"- Abstract: {abstract[: args.abstract_chars]}{'…' if len(abstract) > args.abstract_chars else ''}")
        print()
    print(f"Showing {len(selected)} of {len(rows)} matching candidates.")


def clean_string_list(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SeedingError(f"Decision field '{field}' must be a list of strings.")
    return list(dict.fromkeys(item.strip() for item in value if item.strip()))


def command_apply_decisions(args: argparse.Namespace) -> None:
    vault = normalize_vault(args.vault)
    state = load_state(vault)
    value = load_json(args.decisions)
    decisions = value.get("decisions") if isinstance(value, dict) else value
    if not isinstance(decisions, list):
        raise SeedingError("Decision input must be a list or an object containing decisions.")
    works = state["works"]
    assert isinstance(works, dict)
    changed = 0
    applied = []
    for decision in decisions:
        if not isinstance(decision, dict) or not isinstance(decision.get("openalex_id"), str):
            raise SeedingError("Every decision must contain an openalex_id string.")
        identifier = normalize_openalex_id(decision["openalex_id"])
        candidate = works.get(identifier)
        if not isinstance(candidate, dict):
            raise SeedingError(f"Decision references an unknown candidate: {identifier}")
        screening = candidate.get("screening")
        if not isinstance(screening, dict):
            screening = {}
            candidate["screening"] = screening
        if "label" in decision:
            label = decision["label"]
            if label not in LABELS:
                raise SeedingError(f"Invalid screening label for {identifier}: {label}")
            screening["label"] = label
        if "roles" in decision:
            screening["roles"] = clean_string_list(decision["roles"], "roles")
        if "terms" in decision:
            screening["terms"] = clean_string_list(decision["terms"], "terms")
        if "reason" in decision:
            if not isinstance(decision["reason"], str):
                raise SeedingError("Decision reason must be a string.")
            screening["reason"] = decision["reason"].strip()
        if "selected" in decision:
            if not isinstance(decision["selected"], bool):
                raise SeedingError("Decision selected field must be true or false.")
            candidate["selected"] = decision["selected"]
        if candidate.get("selected") and screening.get("label") not in {"core", "supporting", "contextual"}:
            raise SeedingError(
                f"Selected candidate must be core, supporting, or contextual: {identifier}"
            )
        if (candidate.get("selected") or screening.get("label") == "exclude") and not screening.get("reason"):
            raise SeedingError(f"Selected or excluded candidate requires a reason: {identifier}")
        screening["updated_at"] = utc_now()
        applied.append(
            {
                "openalex_id": identifier,
                "label": screening.get("label"),
                "roles": screening.get("roles") or [],
                "reason": screening.get("reason") or "",
                "terms": screening.get("terms") or [],
                "selected": bool(candidate.get("selected")),
            }
        )
        changed += 1
    state["updated_at"] = utc_now()
    atomic_write_json(vault / "state" / "candidates.json", state)
    append_log(
        vault / "state" / "search-log.jsonl",
        {
            "event": "screening-decisions",
            "executed_at": utc_now(),
            "decision_count": changed,
            "decisions": applied,
        },
    )
    print(f"Applied {changed} decisions.")


def grouped_candidates(works: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for identifier, candidate in works.items():
        if isinstance(candidate, dict):
            candidate = {**candidate, "_id": identifier}
            groups[str(candidate.get("version_key") or identifier)].append(candidate)
    return groups


def command_status(args: argparse.Namespace) -> None:
    vault = normalize_vault(args.vault)
    state = load_state(vault)
    works = state["works"]
    assert isinstance(works, dict)
    labels = Counter()
    stages = Counter()
    abstracts = pdfs = selected_records = 0
    for candidate in works.values():
        if not isinstance(candidate, dict):
            continue
        screening = candidate.get("screening") if isinstance(candidate.get("screening"), dict) else {}
        labels[str(screening.get("label") or "unreviewed")] += 1
        selected_records += int(bool(candidate.get("selected")))
        metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
        abstracts += int(bool(metadata.get("abstract")))
        pdfs += int(bool(metadata.get("has_pdf")))
        for discovery in candidate.get("discovered_by") or []:
            if isinstance(discovery, dict):
                stages[str(discovery.get("stage") or "unknown")] += 1
    groups = grouped_candidates(works)
    selected_groups = sum(
        any(bool(candidate.get("selected")) for candidate in members)
        for members in groups.values()
    )
    summary = {
        "topic": state.get("topic"),
        "target": state.get("target"),
        "candidate_records": len(works),
        "unique_version_groups": len(groups),
        "selected_records": selected_records,
        "selected_unique_papers": selected_groups,
        "labels": dict(sorted(labels.items())),
        "abstracts_available": abstracts,
        "pdfs_reported": pdfs,
        "discovery_occurrences_by_stage": dict(sorted(stages.items())),
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"Topic: {summary['topic']}")
    print(f"Candidates: {len(works)} records / {len(groups)} version groups")
    print(f"Selected: {selected_groups} unique papers (target {state['target']['min']}–{state['target']['max']})")
    print(f"Labels: {dict(sorted(labels.items()))}")
    print(f"Abstracts: {abstracts}; PDFs reported: {pdfs}")
    print(f"Discovery occurrences: {dict(sorted(stages.items()))}")


def preference(candidate: dict[str, object]) -> tuple[object, ...]:
    metadata = candidate.get("metadata") if isinstance(candidate.get("metadata"), dict) else {}
    best = metadata.get("best_oa_location") if isinstance(metadata.get("best_oa_location"), dict) else {}
    return (
        TYPE_PRIORITY.get(str(metadata.get("type")), 0),
        int(bool(metadata.get("doi"))),
        int(best.get("version") == "publishedVersion"),
        int(metadata.get("cited_by_count") or 0),
        int(metadata.get("publication_year") or 0),
    )


def command_finalize(args: argparse.Namespace) -> None:
    vault = normalize_vault(args.vault)
    state = load_state(vault)
    works = state["works"]
    assert isinstance(works, dict)
    queue = []
    collapsed_versions = 0
    for members in grouped_candidates(works).values():
        selected = [candidate for candidate in members if candidate.get("selected")]
        if not selected:
            continue
        eligible = []
        for candidate in members:
            screening = candidate.get("screening") if isinstance(candidate.get("screening"), dict) else {}
            if screening.get("label") != "exclude":
                eligible.append(candidate)
        preferred = max(eligible or selected, key=preference)
        collapsed_versions += max(0, len(selected) - 1)
        screenings = [
            candidate.get("screening")
            for candidate in selected
            if isinstance(candidate.get("screening"), dict)
        ]
        roles = list(
            dict.fromkeys(
                role
                for screening in screenings
                for role in screening.get("roles") or []
            )
        )
        terms = list(
            dict.fromkeys(
                term
                for screening in screenings
                for term in screening.get("terms") or []
            )
        )
        reasons = list(
            dict.fromkeys(
                str(screening.get("reason")).strip()
                for screening in screenings
                if screening.get("reason")
            )
        )
        metadata = preferred.get("metadata") if isinstance(preferred.get("metadata"), dict) else {}
        discovery_ids = list(
            dict.fromkeys(
                str(discovery.get("search_id"))
                for candidate in members
                for discovery in candidate.get("discovered_by") or []
                if isinstance(discovery, dict) and discovery.get("search_id")
            )
        )
        queue.append(
            {
                **metadata,
                "roles": roles,
                "selection_reason": " ".join(reasons),
                "terms": terms,
                "discovered_by": discovery_ids,
                "versions": [str(candidate.get("_id")) for candidate in members],
                "status": "selected-for-ingestion",
            }
        )
    queue.sort(key=lambda item: normalized_title(item.get("title")))
    target = state.get("target") if isinstance(state.get("target"), dict) else {}
    minimum = args.min_papers if args.min_papers is not None else int(target.get("min", 80))
    maximum = args.max_papers if args.max_papers is not None else int(target.get("max", 100))
    if minimum < 1 or maximum < minimum:
        raise SeedingError("Invalid final paper target.")
    if not args.allow_outside_target and not minimum <= len(queue) <= maximum:
        raise SeedingError(
            f"Final selection contains {len(queue)} unique papers; required range is "
            f"{minimum}–{maximum}. Adjust decisions or pass --allow-outside-target explicitly."
        )
    atomic_write_json(vault / "state" / "queue.json", queue)
    append_log(
        vault / "state" / "search-log.jsonl",
        {
            "event": "finalize",
            "executed_at": utc_now(),
            "paper_count": len(queue),
            "target": {"min": minimum, "max": maximum},
            "outside_target_allowed": bool(args.allow_outside_target),
            "collapsed_selected_versions": collapsed_versions,
            "selected_ids": [item.get("openalex_id") for item in queue],
        },
    )
    print(f"Finalized {len(queue)} unique papers in {vault / 'state' / 'queue.json'}")
    print(f"Collapsed duplicate selected versions: {collapsed_versions}")


def add_api_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional .env file containing OPEN_ALEX or OPENALEX_API_KEY.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search OpenAlex and build a screened research-vault seed list."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    search = commands.add_parser("search", help="Run and log one OpenAlex search.")
    search.add_argument("vault", type=Path)
    search.add_argument("--query", required=True)
    search.add_argument("--stage", required=True)
    search.add_argument("--strand", required=True)
    search.add_argument("--rationale", required=True)
    search.add_argument("--per-page", type=positive_count, default=20)
    search.add_argument("--filter", help="Additional comma-separated OpenAlex filters.")
    search.add_argument("--from-year", type=int)
    search.add_argument("--sort", choices=("relevance", "newest", "cited"), default="relevance")
    add_api_options(search)
    search.set_defaults(handler=command_search)

    expand = commands.add_parser(
        "expand-anchor", help="Retrieve all references and recent citing works for an anchor."
    )
    expand.add_argument("vault", type=Path)
    expand.add_argument("--id", required=True, help="OpenAlex work ID or URL.")
    expand.add_argument("--strand", required=True)
    expand.add_argument("--rationale", required=True)
    expand.add_argument("--no-references", action="store_true")
    expand.add_argument("--recent-citing", type=optional_count, default=20)
    expand.add_argument("--from-year", type=int)
    add_api_options(expand)
    expand.set_defaults(handler=command_expand_anchor)

    review = commands.add_parser("review", help="Print a batch of candidates for agent screening.")
    review.add_argument("vault", type=Path)
    review.add_argument("--label", choices=tuple(sorted(LABELS)) + ("any",), default="unreviewed")
    review.add_argument("--search-id")
    review.add_argument("--limit", type=int, default=20)
    review.add_argument("--offset", type=int, default=0)
    review.add_argument("--abstract-chars", type=int, default=700)
    review.add_argument("--format", choices=("markdown", "json"), default="markdown")
    review.set_defaults(handler=command_review)

    decisions = commands.add_parser(
        "apply-decisions", help="Validate and apply agent screening decisions from JSON."
    )
    decisions.add_argument("vault", type=Path)
    decisions.add_argument("decisions", type=Path)
    decisions.set_defaults(handler=command_apply_decisions)

    status = commands.add_parser("status", help="Report seeding progress and coverage counts.")
    status.add_argument("vault", type=Path)
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=command_status)

    finalize = commands.add_parser(
        "finalize", help="Deduplicate selected versions and write state/queue.json."
    )
    finalize.add_argument("vault", type=Path)
    finalize.add_argument("--min-papers", type=int)
    finalize.add_argument("--max-papers", type=int)
    finalize.add_argument("--allow-outside-target", action="store_true")
    finalize.set_defaults(handler=command_finalize)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.handler(args)
    except (SeedingError, OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
