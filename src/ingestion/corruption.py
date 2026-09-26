from __future__ import annotations

from datetime import UTC, datetime
from math import ceil
from pathlib import Path

import pandas as pd

from core.utils import write_json


NOISE = "zxqv corruption-noise-9f3a " * 40


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Apply six deterministic corruption scenarios and write an audit log."""
    required = {
        "paper_id",
        "title",
        "summary",
        "authors_joined",
        "categories_joined",
        "published",
        "age_days",
        "text_for_embedding",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Corruption requires columns: {', '.join(missing)}")
    if len(df) < 6:
        raise ValueError("At least six rows are required for the corruption suite.")

    working = df.copy(deep=True)
    working["published"] = working["published"].astype(str)
    working = working.sort_values(
        ["published", "paper_id"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)
    scenarios: list[dict] = []

    drop_count = max(1, ceil(len(working) * 0.20))
    dropped_ids = working.iloc[:drop_count]["paper_id"].astype(str).tolist()
    working = working.iloc[drop_count:].reset_index(drop=True)
    scenarios.append(_event("drop_latest_records", dropped_ids, "Removed latest 20% of rows"))

    affected_count = max(1, ceil(len(working) * 0.30))
    target_indexes = list(range(min(affected_count, len(working))))

    blank_ids = working.loc[target_indexes, "paper_id"].astype(str).tolist()
    working.loc[target_indexes, "summary"] = ""
    scenarios.append(_event("blank_summary", blank_ids, "Replaced summaries with empty strings"))

    noise_indexes = list(range(0, len(working), 2))
    noise_ids = working.loc[noise_indexes, "paper_id"].astype(str).tolist()
    working.loc[noise_indexes, "summary"] = (
        working.loc[noise_indexes, "summary"].astype(str) + " " + NOISE
    ).str.strip()
    scenarios.append(_event("inject_noise", noise_ids, "Injected repeated out-of-domain tokens"))

    truncated_ids = working.loc[target_indexes, "paper_id"].astype(str).tolist()
    working.loc[target_indexes, "title"] = (
        working.loc[target_indexes, "title"].astype(str).str.slice(0, 7)
    )
    scenarios.append(_event("truncate_title", truncated_ids, "Truncated titles to fewer than 8 characters"))

    stale_count = max(1, ceil(len(working) * 0.40))
    stale_indexes = list(range(len(working) - stale_count, len(working)))
    stale_ids = working.loc[stale_indexes, "paper_id"].astype(str).tolist()
    working.loc[stale_indexes, "published"] = "2000-01-01"
    working.loc[stale_indexes, "age_days"] = 9_999
    scenarios.append(_event("stale_date", stale_ids, "Moved publication dates beyond the freshness SLA"))

    duplicate_count = max(1, ceil(len(working) * 0.20))
    duplicate_rows = working.iloc[-duplicate_count:].copy(deep=True)
    duplicate_ids = duplicate_rows["paper_id"].astype(str).tolist()
    working = pd.concat([working, duplicate_rows], ignore_index=True)
    scenarios.append(_event("duplicate_rows", duplicate_ids, "Appended duplicate paper identities"))

    working["summary_chars"] = working["summary"].astype(str).str.len()
    working["text_for_embedding"] = working.apply(_embedding_text, axis=1)

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "deterministic": True,
        "input_rows": int(len(df)),
        "output_rows": int(len(working)),
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }
    write_json(Path(output_log_path), payload)
    return working.reset_index(drop=True)


def _embedding_text(row: pd.Series) -> str:
    return "\n".join(
        [
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Published: {row['published']}",
            f"Categories: {row['categories_joined']}",
            f"Summary: {row['summary']}",
        ]
    )


def _event(name: str, paper_ids: list[str], description: str) -> dict:
    return {
        "scenario": name,
        "description": description,
        "affected_rows": len(paper_ids),
        "paper_ids": paper_ids,
    }
