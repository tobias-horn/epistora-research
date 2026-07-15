#!/usr/bin/env python3
"""Acquire content for a shortlist and finalize its validated source queue."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen


API_ROOT = "https://api.openalex.org"
CONTENT_ROOT = "https://content.openalex.org/works"
CONTENT_PRICE_USD = Decimal("0.01")
FORMAT_DETAILS = {
    "pdf": {"availability": "pdf", "extension": "pdf", "filename": "paper.pdf"},
    "xml": {
        "availability": "grobid_xml",
        "extension": "grobid-xml",
        "filename": "fulltext.tei.xml",
    },
}
OPENALEX_SOURCE = "openalex-content-api"
EXTERNAL_SOURCE = "openalex-oa-location"


class AcquisitionError(RuntimeError):
    """Raised when acquisition state or an OpenAlex operation is invalid."""


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
        raise AcquisitionError(f"Required file is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise AcquisitionError(f"Invalid JSON in {path}: {error}") from error


def normalize_vault(raw: Path) -> Path:
    vault = Path(os.path.abspath(raw.expanduser()))
    required = (vault / "state" / "research.md", vault / "state" / "shortlist.json")
    if not vault.is_dir() or any(not path.is_file() for path in required):
        raise AcquisitionError(f"Not an initialized research vault: {vault}")
    return vault


def normalize_work_id(raw: object) -> str:
    identifier = str(raw or "").strip().rstrip("/").rsplit("/", 1)[-1].upper()
    if not re.fullmatch(r"W\d+", identifier):
        raise AcquisitionError(f"Invalid OpenAlex work ID in queue: {raw}")
    return identifier


def load_shortlist(vault: Path) -> tuple[list[dict[str, object]], list[str]]:
    value = load_json(vault / "state" / "shortlist.json")
    if not isinstance(value, list) or not value:
        raise AcquisitionError(
            "state/shortlist.json is empty or invalid; build the shortlist first."
        )
    records: list[dict[str, object]] = []
    identifiers: list[str] = []
    for item in value:
        if not isinstance(item, dict):
            raise AcquisitionError("Every shortlist entry must be a JSON object.")
        identifier = normalize_work_id(item.get("openalex_id"))
        records.append(item)
        identifiers.append(identifier)
    if len(set(identifiers)) != len(identifiers):
        raise AcquisitionError("state/shortlist.json contains duplicate OpenAlex work IDs.")
    return records, identifiers


def shortlist_fingerprint(identifiers: list[str]) -> str:
    encoded = json.dumps(sorted(identifiers), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def user_config_env_file() -> Path:
    configured = os.environ.get("XDG_CONFIG_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".config"
    return Path(os.path.abspath(base)) / "research-vault" / ".env"


def resolve_api_key(vault: Path, env_file: Path | None) -> str:
    if env_file is not None:
        load_env_file(Path(os.path.abspath(env_file.expanduser())))
    else:
        for candidate in (
            Path.cwd() / ".env",
            vault / ".env",
            vault.parent / ".env",
            user_config_env_file(),
        ):
            load_env_file(candidate)
    key = os.environ.get("OPEN_ALEX") or os.environ.get("OPENALEX_API_KEY")
    if not key:
        raise AcquisitionError(
            "OpenAlex API key not found. Configure it once by running: "
            f"python3 {shlex.quote(str(vault / 'scripts' / 'configure_openalex.py'))} "
            "or pass --env-file. Never paste the key into chat."
        )
    return key


def safe_http_error(error: HTTPError) -> str:
    return f"HTTP {error.code}"


def request_json(endpoint: str, params: dict[str, object], api_key: str) -> dict[str, object]:
    url = f"{API_ROOT}/{endpoint.lstrip('/')}?" + urlencode(
        {**params, "api_key": api_key}
    )
    request = Request(url, headers={"User-Agent": "research-vault/0.2"})
    last_error = "unknown error"
    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise AcquisitionError("OpenAlex returned a non-object response.")
            return payload
        except HTTPError as error:
            last_error = safe_http_error(error)
            if error.code not in {429, 500, 502, 503, 504}:
                break
        except (URLError, TimeoutError) as error:
            last_error = f"network error: {error.reason if isinstance(error, URLError) else error}"
        if attempt < 2:
            time.sleep(2**attempt)
    raise AcquisitionError(f"OpenAlex metadata request failed after retries: {last_error}")


def batches(values: list[str], size: int = 100) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def fetch_metadata(identifiers: list[str], api_key: str) -> dict[str, dict[str, object]]:
    works: dict[str, dict[str, object]] = {}
    for chunk in batches(identifiers):
        payload = request_json(
            "works",
            {"filter": "openalex:" + "|".join(chunk), "per_page": len(chunk)},
            api_key,
        )
        results = payload.get("results")
        if not isinstance(results, list):
            raise AcquisitionError("OpenAlex metadata response is missing results.")
        for work in results:
            if not isinstance(work, dict):
                continue
            identifier = normalize_work_id(work.get("id"))
            if identifier in identifiers:
                works[identifier] = work
    missing = [identifier for identifier in identifiers if identifier not in works]
    if missing:
        preview = ", ".join(missing[:10])
        suffix = "..." if len(missing) > 10 else ""
        raise AcquisitionError(f"OpenAlex returned no metadata for: {preview}{suffix}")
    return works


def work_directory(vault: Path, identifier: str) -> Path:
    return vault / "raw" / "works" / identifier


def safe_web_url(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return value


def external_pdf_location(work: dict[str, object]) -> dict[str, object] | None:
    candidates: list[object] = [work.get("best_oa_location")]
    candidates.extend(work.get("locations") or [])
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict) or candidate.get("is_oa") is not True:
            continue
        url = safe_web_url(candidate.get("pdf_url"))
        if not url or url in seen:
            continue
        seen.add(url)
        source = candidate.get("source") if isinstance(candidate.get("source"), dict) else {}
        return {
            "url": url,
            "license": candidate.get("license"),
            "version": candidate.get("version"),
            "host": urlparse(url).hostname,
            "source_id": source.get("id"),
        }
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_content(path: Path, content_format: str) -> bool:
    if not path.is_file():
        return False
    try:
        if content_format == "pdf":
            if path.stat().st_size < 1024:
                return False
            with path.open("rb") as handle:
                return handle.read(5) == b"%PDF-"
        return path.stat().st_size > 0
    except OSError:
        return False


def decompress_xml_if_needed(path: Path) -> None:
    with path.open("rb") as handle:
        prefix = handle.read(2)
    if prefix == b"\x1f\x8b":
        path.write_bytes(gzip.decompress(path.read_bytes()))


def content_record(
    vault: Path,
    identifier: str,
    content_format: str,
    available: bool,
    source: str | None,
    previous: object,
) -> dict[str, object]:
    details = FORMAT_DETAILS[content_format]
    relative_path = Path("raw") / "works" / identifier / str(details["filename"])
    absolute_path = vault / relative_path
    prior = previous if isinstance(previous, dict) else {}
    if valid_content(absolute_path, content_format):
        return {
            "available": available,
            "status": "downloaded",
            "source": prior.get("source") or source,
            "path": str(relative_path),
            "retrieved_at": prior.get("retrieved_at"),
            "size_bytes": absolute_path.stat().st_size,
            "sha256": sha256_file(absolute_path),
            "attempts": int(prior.get("attempts") or 0),
            "last_error": None,
        }
    return {
        "available": available,
        "status": "pending" if available else "unavailable",
        "source": source,
        "path": str(relative_path),
        "retrieved_at": None,
        "size_bytes": None,
        "sha256": None,
        "attempts": int(prior.get("attempts") or 0),
        "last_error": None,
    }


def load_acquisition_state(vault: Path, required: bool = True) -> dict[str, object]:
    path = vault / "state" / "acquisition.json"
    if not path.is_file() and not required:
        return {}
    value = load_json(path)
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise AcquisitionError("state/acquisition.json has an unsupported schema.")
    if not isinstance(value.get("works"), dict):
        raise AcquisitionError("state/acquisition.json must contain a works object.")
    return value


def summarize(state: dict[str, object]) -> dict[str, object]:
    works = state.get("works") if isinstance(state.get("works"), dict) else {}
    summary: dict[str, object] = {"papers": len(works)}
    for content_format in FORMAT_DETAILS:
        counts = {
            "available": 0,
            "pending": 0,
            "downloaded": 0,
            "failed": 0,
            "unavailable": 0,
            "openalex_source": 0,
            "external_source": 0,
        }
        for work in works.values():
            if not isinstance(work, dict):
                continue
            record = work.get(content_format)
            if not isinstance(record, dict):
                continue
            counts["available"] += int(bool(record.get("available")))
            if record.get("available") and record.get("source") == OPENALEX_SOURCE:
                counts["openalex_source"] += 1
            elif record.get("available") and record.get("source") == EXTERNAL_SOURCE:
                counts["external_source"] += 1
            status = str(record.get("status") or "pending")
            if status in counts:
                counts[status] += 1
        paid_pending = sum(
            1
            for work in works.values()
            if isinstance(work, dict)
            and isinstance(work.get(content_format), dict)
            and work[content_format].get("status") == "pending"
            and work[content_format].get("source") == OPENALEX_SOURCE
        )
        counts["estimated_missing_cost_usd"] = str(CONTENT_PRICE_USD * paid_pending)
        summary[content_format] = counts
    summary["qualified_papers"] = sum(
        1
        for work in works.values()
        if isinstance(work, dict)
        and any(
            isinstance(work.get(content_format), dict)
            and work[content_format].get("status") == "downloaded"
            for content_format in FORMAT_DETAILS
        )
    )
    return summary


def command_plan(args: argparse.Namespace) -> None:
    vault = normalize_vault(args.vault)
    shortlist, identifiers = load_shortlist(vault)
    api_key = resolve_api_key(vault, args.env_file)
    metadata = fetch_metadata(identifiers, api_key)
    previous_state = load_acquisition_state(vault, required=False)
    previous_works = (
        previous_state.get("works") if isinstance(previous_state.get("works"), dict) else {}
    )
    planned_at = utc_now()
    state_works: dict[str, object] = {}
    shortlist_by_id = {normalize_work_id(item.get("openalex_id")): item for item in shortlist}
    for identifier in identifiers:
        work = metadata[identifier]
        directory = work_directory(vault, identifier)
        directory.mkdir(parents=True, exist_ok=True)
        metadata_path = directory / "metadata.openalex.json"
        atomic_write_json(metadata_path, work)
        content = work.get("has_content") if isinstance(work.get("has_content"), dict) else {}
        external_pdf = external_pdf_location(work)
        pdf_source = OPENALEX_SOURCE if content.get("pdf") else (
            EXTERNAL_SOURCE if external_pdf else None
        )
        previous = previous_works.get(identifier)
        previous = previous if isinstance(previous, dict) else {}
        best_location = (
            work.get("best_oa_location")
            if isinstance(work.get("best_oa_location"), dict)
            else {}
        )
        state_works[identifier] = {
            "title": work.get("display_name") or shortlist_by_id[identifier].get("title"),
            "license": (
                external_pdf.get("license")
                if pdf_source == EXTERNAL_SOURCE and external_pdf
                else best_location.get("license")
            ),
            "metadata": {
                "status": "downloaded",
                "path": str(metadata_path.relative_to(vault)),
                "retrieved_at": planned_at,
                "openalex_updated_date": work.get("updated_date"),
                "size_bytes": metadata_path.stat().st_size,
                "sha256": sha256_file(metadata_path),
            },
            "pdf": content_record(
                vault,
                identifier,
                "pdf",
                pdf_source is not None,
                pdf_source,
                previous.get("pdf"),
            ),
            "xml": content_record(
                vault,
                identifier,
                "xml",
                bool(content.get("grobid_xml")),
                OPENALEX_SOURCE if content.get("grobid_xml") else None,
                previous.get("xml"),
            ),
        }
    created_at = previous_state.get("created_at") or planned_at
    state = {
        "schema_version": 1,
        "created_at": created_at,
        "updated_at": planned_at,
        "planned_at": planned_at,
        "shortlist_fingerprint": shortlist_fingerprint(identifiers),
        "content_price_usd": str(CONTENT_PRICE_USD),
        "works": state_works,
    }
    atomic_write_json(vault / "state" / "acquisition.json", state)
    summary = summarize(state)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"Acquisition plan refreshed for {len(identifiers)} papers.")
    print(f"Metadata saved under {vault / 'raw' / 'works'}")
    for content_format in FORMAT_DETAILS:
        counts = summary[content_format]
        assert isinstance(counts, dict)
        print(
            f"{content_format.upper()}: {counts['available']} available, "
            f"{counts['openalex_source']} from OpenAlex, "
            f"{counts['external_source']} from external OA locations, "
            f"{counts['downloaded']} already downloaded, {counts['pending']} pending "
            f"(${counts['estimated_missing_cost_usd']})"
        )


def parse_formats(raw: str) -> tuple[str, ...]:
    values = tuple(dict.fromkeys(part.strip().lower() for part in raw.split(",") if part.strip()))
    if not values or any(value not in FORMAT_DETAILS for value in values):
        raise argparse.ArgumentTypeError("formats must be pdf, xml, or pdf,xml")
    return values


def parse_money(raw: str) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation as error:
        raise argparse.ArgumentTypeError("must be a dollar amount") from error
    if value < 0:
        raise argparse.ArgumentTypeError("must not be negative")
    return value


def download_url(
    destination: Path,
    url: str,
    content_format: str,
    headers: dict[str, str],
) -> tuple[int, str, str | None]:
    request = Request(url, headers=headers)
    temporary = destination.with_name(destination.name + ".part")
    temporary.unlink(missing_ok=True)
    try:
        with urlopen(request, timeout=120) as response, temporary.open("wb") as handle:
            if safe_web_url(response.geturl()) is None:
                raise AcquisitionError("Download redirected to a non-web URL.")
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
            content_type = response.headers.get("Content-Type")
        if content_format == "xml":
            decompress_xml_if_needed(temporary)
        if not valid_content(temporary, content_format):
            raise AcquisitionError(f"Downloaded {content_format.upper()} failed validation.")
        temporary.replace(destination)
        return destination.stat().st_size, sha256_file(destination), content_type
    finally:
        temporary.unlink(missing_ok=True)


def download_openalex_content(
    destination: Path, identifier: str, content_format: str, api_key: str
) -> tuple[int, str, str | None]:
    extension = FORMAT_DETAILS[content_format]["extension"]
    url = f"{CONTENT_ROOT}/{identifier}.{extension}?" + urlencode({"api_key": api_key})
    return download_url(
        destination,
        url,
        content_format,
        {"User-Agent": "research-vault/0.3"},
    )


def download_external_pdf(
    destination: Path, url: str
) -> tuple[int, str, str | None]:
    if safe_web_url(url) is None:
        raise AcquisitionError("OpenAlex supplied an invalid external PDF URL.")
    return download_url(
        destination,
        url,
        "pdf",
        {
            "User-Agent": "research-vault/0.3",
            "Accept": "application/pdf,*/*;q=0.8",
        },
    )


def require_current_plan(vault: Path) -> tuple[dict[str, object], list[str]]:
    _, identifiers = load_shortlist(vault)
    state = load_acquisition_state(vault)
    if state.get("shortlist_fingerprint") != shortlist_fingerprint(identifiers):
        raise AcquisitionError("The acquisition plan is stale; run plan again.")
    return state, identifiers


def command_run(args: argparse.Namespace) -> None:
    vault = normalize_vault(args.vault)
    state, identifiers = require_current_plan(vault)
    works = state["works"]
    assert isinstance(works, dict)
    requests: list[tuple[str, str, str]] = []
    for identifier in identifiers:
        work = works.get(identifier)
        if not isinstance(work, dict):
            raise AcquisitionError(f"Acquisition plan is missing {identifier}; run plan again.")
        for content_format in args.formats:
            record = work.get(content_format)
            if isinstance(record, dict) and record.get("available") and record.get("status") != "downloaded":
                source = str(record.get("source") or "")
                if source not in {OPENALEX_SOURCE, EXTERNAL_SOURCE}:
                    raise AcquisitionError("Acquisition source is missing; run plan again.")
                requests.append((identifier, content_format, source))
    paid_requests = sum(source == OPENALEX_SOURCE for _, _, source in requests)
    external_requests = sum(source == EXTERNAL_SOURCE for _, _, source in requests)
    estimate = CONTENT_PRICE_USD * paid_requests
    if estimate > args.max_cost_usd:
        raise AcquisitionError(
            f"Run would make {paid_requests} paid OpenAlex content requests "
            f"(estimated ${estimate}), exceeding "
            f"--max-cost-usd {args.max_cost_usd}."
        )
    print(
        f"Downloading {len(requests)} files: {paid_requests} from OpenAlex content "
        f"and {external_requests} from external OA locations "
        f"(estimated OpenAlex maximum ${estimate})."
    )
    api_key = resolve_api_key(vault, args.env_file) if paid_requests else None
    failures = 0
    downloaded = 0
    for identifier, content_format, source in requests:
        work = works[identifier]
        assert isinstance(work, dict)
        record = work[content_format]
        assert isinstance(record, dict)
        destination = vault / str(record["path"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        record["attempts"] = int(record.get("attempts") or 0) + 1
        try:
            if source == OPENALEX_SOURCE:
                assert api_key is not None
                size, checksum, content_type = download_openalex_content(
                    destination, identifier, content_format, api_key
                )
            else:
                metadata = load_json(vault / str(work["metadata"]["path"]))
                if not isinstance(metadata, dict):
                    raise AcquisitionError(f"Invalid saved metadata for {identifier}.")
                location = external_pdf_location(metadata)
                if not location:
                    raise AcquisitionError(
                        "The planned external PDF location is no longer present; run plan again."
                    )
                size, checksum, content_type = download_external_pdf(
                    destination, str(location["url"])
                )
            record.update(
                {
                    "status": "downloaded",
                    "retrieved_at": utc_now(),
                    "size_bytes": size,
                    "sha256": checksum,
                    "content_type": content_type,
                    "source": source,
                    "last_error": None,
                }
            )
            downloaded += 1
            print(f"Downloaded {identifier} {content_format.upper()} via {source}")
        except HTTPError as error:
            record.update({"status": "failed", "last_error": safe_http_error(error)})
            failures += 1
            print(f"Failed {identifier} {content_format.upper()}: {safe_http_error(error)}", file=sys.stderr)
        except (URLError, TimeoutError, OSError, AcquisitionError) as error:
            message = (
                f"network error: {error.reason}"
                if isinstance(error, URLError)
                else str(error)
            )
            record.update({"status": "failed", "last_error": message})
            failures += 1
            print(f"Failed {identifier} {content_format.upper()}: {message}", file=sys.stderr)
        state["updated_at"] = utc_now()
        state["last_run_at"] = state["updated_at"]
        atomic_write_json(vault / "state" / "acquisition.json", state)
    possible = len(identifiers) * len(args.formats)
    print(f"Downloaded: {downloaded}; failed: {failures}; skipped: {possible - len(requests)}")
    if failures:
        raise AcquisitionError("Some downloads failed; inspect status and rerun when ready.")


def command_status(args: argparse.Namespace) -> None:
    vault = normalize_vault(args.vault)
    state, _ = require_current_plan(vault)
    summary = summarize(state)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(f"Papers: {summary['papers']}; qualified with PDF or XML: {summary['qualified_papers']}")
    for content_format in FORMAT_DETAILS:
        counts = summary[content_format]
        assert isinstance(counts, dict)
        print(
            f"{content_format.upper()}: {counts['downloaded']} downloaded, "
            f"{counts['pending']} pending, {counts['failed']} failed, "
            f"{counts['unavailable']} unavailable "
            f"({counts['openalex_source']} OpenAlex, "
            f"{counts['external_source']} external OA)"
        )


def command_finalize(args: argparse.Namespace) -> None:
    vault = normalize_vault(args.vault)
    state, identifiers = require_current_plan(vault)
    shortlist, _ = load_shortlist(vault)
    works = state["works"]
    assert isinstance(works, dict)
    shortlist_by_id = {normalize_work_id(item.get("openalex_id")): item for item in shortlist}
    queue = []
    for identifier in identifiers:
        work = works.get(identifier)
        if not isinstance(work, dict):
            continue
        artifacts = {
            content_format: record.get("path")
            for content_format in FORMAT_DETAILS
            if isinstance((record := work.get(content_format)), dict)
            and record.get("status") == "downloaded"
            and valid_content(vault / str(record.get("path")), content_format)
        }
        if not artifacts:
            continue
        queue.append(
            {
                **shortlist_by_id[identifier],
                "status": "ready-for-ingestion",
                "artifacts": artifacts,
            }
        )
    candidates = load_json(vault / "state" / "candidates.json")
    target = candidates.get("target") if isinstance(candidates, dict) and isinstance(candidates.get("target"), dict) else {}
    minimum = args.min_papers if args.min_papers is not None else int(target.get("min", 80))
    maximum = args.max_papers if args.max_papers is not None else int(target.get("max", 100))
    if minimum < 1 or maximum < minimum:
        raise AcquisitionError("Invalid final queue target.")
    if not args.allow_outside_target and not minimum <= len(queue) <= maximum:
        raise AcquisitionError(
            f"Only {len(queue)} shortlisted papers have a validated PDF or downloaded XML; required "
            f"range is {minimum}–{maximum}. Add targeted replacements and rebuild the "
            "shortlist, or explicitly allow a smaller final queue."
        )
    atomic_write_json(vault / "state" / "queue.json", queue)
    print(f"Finalized {len(queue)} retained sources in {vault / 'state' / 'queue.json'}")
    print(f"Excluded without a validated PDF or downloaded XML: {len(shortlist) - len(queue)}")


def add_api_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional .env file containing OPEN_ALEX or OPENALEX_API_KEY.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquire OpenAlex metadata, cached content, and external OA PDFs."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser(
        "plan", help="Refresh metadata and calculate cached/external availability and cost."
    )
    plan.add_argument("vault", type=Path)
    plan.add_argument("--json", action="store_true")
    add_api_options(plan)
    plan.set_defaults(handler=command_plan)

    run = commands.add_parser("run", help="Download cached OpenAlex content and external OA PDFs.")
    run.add_argument("vault", type=Path)
    run.add_argument(
        "--formats",
        type=parse_formats,
        default=("pdf", "xml"),
        help="Formats to retrieve (default: pdf,xml).",
    )
    run.add_argument("--max-cost-usd", type=parse_money, required=True)
    add_api_options(run)
    run.set_defaults(handler=command_run)

    status = commands.add_parser("status", help="Report acquisition progress.")
    status.add_argument("vault", type=Path)
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=command_status)

    finalize = commands.add_parser(
        "finalize", help="Write queue.json using papers with a validated PDF or downloaded XML."
    )
    finalize.add_argument("vault", type=Path)
    finalize.add_argument("--min-papers", type=int)
    finalize.add_argument("--max-papers", type=int)
    finalize.add_argument("--allow-outside-target", action="store_true")
    finalize.set_defaults(handler=command_finalize)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        args.handler(args)
    except (AcquisitionError, OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
