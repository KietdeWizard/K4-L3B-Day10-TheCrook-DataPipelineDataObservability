from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Build the deterministic, deduplicated dataframe used by the RAG index."""
    if not records:
        raise ValueError("At least one raw paper record is required.")

    run_timestamp = pd.Timestamp(run_date)
    if run_timestamp.tzinfo is None:
        run_timestamp = run_timestamp.tz_localize("UTC")
    else:
        run_timestamp = run_timestamp.tz_convert("UTC")

    cleaned_rows: list[dict[str, Any]] = []
    for record in records:
        paper_id = normalize_whitespace(record.paper_id)
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)
        if not paper_id or not title or not summary:
            continue

        published_timestamp = pd.to_datetime(record.published, errors="coerce", utc=True)
        if pd.isna(published_timestamp):
            continue

        authors = _clean_list(record.authors)
        categories = _clean_list(record.categories)
        authors_joined = ", ".join(authors) or "Unknown"
        categories_joined = ", ".join(categories) or "Uncategorized"
        published = published_timestamp.date().isoformat()
        updated_timestamp = pd.to_datetime(record.updated, errors="coerce", utc=True)
        updated = (
            updated_timestamp.date().isoformat()
            if not pd.isna(updated_timestamp)
            else published
        )
        age_days = int((run_timestamp.normalize() - published_timestamp.normalize()).days)
        text_for_embedding = "\n".join(
            [
                f"Title: {title}",
                f"Authors: {authors_joined}",
                f"Published: {published}",
                f"Categories: {categories_joined}",
                f"Summary: {summary}",
            ]
        )

        cleaned_rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": normalize_whitespace(record.primary_category)
                or categories_joined.split(",", maxsplit=1)[0],
                "published": published,
                "updated": updated,
                "abs_url": normalize_whitespace(record.abs_url),
                "pdf_url": normalize_whitespace(record.pdf_url),
                "comment": normalize_whitespace(record.comment),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "age_days": age_days,
                "text_for_embedding": text_for_embedding,
            }
        )

    if not cleaned_rows:
        raise ValueError("No valid rows remained after cleaning.")

    dataframe = pd.DataFrame(cleaned_rows)
    dataframe = dataframe.drop_duplicates(subset=["paper_id"], keep="first")
    dataframe = dataframe.sort_values(
        by=["published", "paper_id"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)
    return dataframe


def _clean_list(values: object) -> list[str]:
    if not isinstance(values, (list, tuple)):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = normalize_whitespace(str(value or ""))
        key = item.casefold()
        if item and key not in seen:
            cleaned.append(item)
            seen.add(key)
    return cleaned
