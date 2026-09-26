from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from html import unescape
from pathlib import Path
import re
import time

import requests
from requests.exceptions import RequestException

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json


CROSSREF_WORKS_URL = "https://api.crossref.org/works"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref response into the stable raw-record contract."""
    if not isinstance(payload, dict):
        raise ValueError("Crossref payload must be a JSON object.")

    message = payload.get("message", {})
    items = message.get("items", []) if isinstance(message, dict) else []
    if not isinstance(items, list):
        raise ValueError("Crossref payload is missing message.items list.")

    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue

        paper_id = normalize_whitespace(str(item.get("DOI", "")))
        titles = item.get("title") or []
        title = _clean_text(titles[0] if isinstance(titles, list) and titles else titles)
        if not paper_id or not title or paper_id.lower() in seen_ids:
            continue

        summary = _clean_text(item.get("abstract", ""))
        authors = _parse_authors(item.get("author", []))
        categories = [
            cleaned
            for value in (item.get("subject") or [])
            if (cleaned := _clean_text(value))
        ]
        published = _parse_crossref_date(item.get("published"))
        updated = _parse_updated_date(item) or published
        abs_url = normalize_whitespace(str(item.get("URL", ""))) or f"https://doi.org/{paper_id}"
        pdf_url = _find_pdf_url(item.get("link")) or abs_url

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=categories[0] if categories else "Uncategorized",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=f"Crossref record {paper_id}",
            )
        )
        seen_ids.add(paper_id.lower())

    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Load the preserved snapshot or refresh it from Crossref with fallback."""
    snapshot_path = settings.paths.raw_api_response
    payload: dict | None = None

    if snapshot_path.exists() and not settings.refresh_source:
        payload = read_json(snapshot_path)
    else:
        try:
            payload = _fetch_crossref_payload(settings)
            # Preserve only a successfully decoded Crossref response.
            write_json(snapshot_path, payload)
        except (RequestException, ValueError) as exc:
            if not snapshot_path.exists():
                raise RuntimeError("Crossref request failed and no offline snapshot is available.") from exc
            print(f"Crossref unavailable; using offline snapshot: {exc}")
            payload = read_json(snapshot_path)

    records = parse_crossref_payload(payload)
    if not records:
        raise ValueError("Crossref payload produced no valid paper records.")

    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load the preserved normalized records as ``PaperRecord`` objects."""
    payload = read_json(Path(path))
    if not isinstance(payload, list):
        raise ValueError(f"Raw records file must contain a JSON list: {path}")
    records = [PaperRecord(**item) for item in payload if isinstance(item, dict)]
    if not records:
        raise ValueError(f"Raw records file contains no records: {path}")
    return records


def _clean_text(value: object) -> str:
    text = unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize_whitespace(text)


def _parse_authors(payload: object) -> list[str]:
    if not isinstance(payload, list):
        return []
    authors: list[str] = []
    for author in payload:
        if not isinstance(author, dict):
            continue
        name = normalize_whitespace(f"{author.get('given', '')} {author.get('family', '')}")
        if name:
            authors.append(name)
    return authors


def _parse_crossref_date(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    date_parts = payload.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts or not isinstance(date_parts[0], list):
        return ""
    parts = date_parts[0]
    if not parts:
        return ""
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day).isoformat()
    except (TypeError, ValueError):
        return ""


def _parse_updated_date(item: dict) -> str:
    for field in ("indexed", "created", "deposited"):
        value = item.get(field)
        if not isinstance(value, dict):
            continue
        date_time = normalize_whitespace(str(value.get("date-time", "")))
        if date_time:
            return date_time[:10]
        parsed = _parse_crossref_date(value)
        if parsed:
            return parsed
    return ""


def _find_pdf_url(payload: object) -> str:
    if not isinstance(payload, list):
        return ""
    for link in payload:
        if not isinstance(link, dict):
            continue
        content_type = str(link.get("content-type", "")).lower()
        url = normalize_whitespace(str(link.get("URL", "")))
        if url and ("pdf" in content_type or url.lower().endswith(".pdf")):
            return url
    return ""


def _fetch_crossref_payload(settings: Settings) -> dict:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    headers = {"User-Agent": "Day10DataObservabilityLab/1.0 (educational use)"}
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            response = requests.get(
                CROSSREF_WORKS_URL,
                params=params,
                headers=headers,
                timeout=30,
            )
            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt < 2:
                    time.sleep(2**attempt)
                    continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("message"), dict):
                raise ValueError("Crossref returned an invalid JSON payload.")
            return payload
        except (RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2**attempt)

    if isinstance(last_error, RequestException):
        raise last_error
    raise ValueError(f"Crossref request failed: {last_error}")
