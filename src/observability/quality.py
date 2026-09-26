from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json


MAX_STALE_RATIO = 0.25


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Validate the clean-data contract with the Great Expectations 1.x API."""
    required_columns = {"paper_id", "title", "summary", "age_days"}
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"Quality checks require columns: {', '.join(missing_columns)}")

    # Import locally so non-quality helpers remain usable in lightweight tooling.
    import great_expectations as gx

    safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", report_name).strip("_") or "quality"
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name=f"papers_source_{safe_name}")
    data_asset = data_source.add_dataframe_asset(name=f"papers_asset_{safe_name}")
    batch_definition = data_asset.add_batch_definition_whole_dataframe(
        f"papers_batch_{safe_name}"
    )
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    # Five validations cover the four mandatory expectation types; the not-null
    # expectation is deliberately applied to both identity and title columns.
    expectations = [
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=1,
            max_value=max(settings.max_results * 2, 1),
        ),
        gx.expectations.ExpectColumnValuesToNotBeNull(column="paper_id"),
        gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"),
        gx.expectations.ExpectColumnValuesToNotBeNull(column="title"),
        gx.expectations.ExpectColumnValueLengthsToBeBetween(
            column="summary",
            min_value=20,
            max_value=20_000,
        ),
    ]

    checks: list[dict[str, Any]] = []
    for expectation in expectations:
        validation = batch.validate(expectation)
        raw_result = validation.to_json_dict()
        configuration = raw_result.get("expectation_config", {})
        checks.append(
            {
                "expectation_type": configuration.get(
                    "type", expectation.__class__.__name__
                ),
                "kwargs": configuration.get("kwargs", {}),
                "success": bool(validation.success),
                "result": raw_result.get("result", {}),
            }
        )

    successful = sum(1 for check in checks if check["success"])
    payload = {
        "report_name": report_name,
        "engine": "great_expectations",
        "great_expectations_version": gx.__version__,
        "generated_at": datetime.now(UTC).isoformat(),
        "rows": int(len(df)),
        "success": successful == len(checks),
        "statistics": {
            "evaluated_expectations": len(checks),
            "successful_expectations": successful,
            "unsuccessful_expectations": len(checks) - successful,
            "success_percent": (successful / len(checks) * 100.0) if checks else 0.0,
        },
        "checks": checks,
    }
    write_json(settings.paths.quality_dir / f"{safe_name}_quality_report.json", payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Measure the 180-day/25% freshness SLA and persist its evidence."""
    required_columns = {"published", "age_days"}
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        raise ValueError(f"Freshness report requires columns: {', '.join(missing_columns)}")

    published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    ages = pd.to_numeric(df["age_days"], errors="coerce")
    total_rows = int(len(df))
    invalid_date_rows = int(published.isna().sum())
    invalid_age_rows = int(ages.isna().sum())
    stale_mask = ages.gt(settings.freshness_threshold_days) | ages.isna()
    stale_rows = int(stale_mask.sum())
    stale_ratio = stale_rows / total_rows if total_rows else 1.0

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "threshold_days": settings.freshness_threshold_days,
        "max_stale_ratio": MAX_STALE_RATIO,
        "latest_published": _date_string(published.max()),
        "oldest_published": _date_string(published.min()),
        "stale_rows": stale_rows,
        "stale_ratio": stale_ratio,
        "total_rows": total_rows,
        "invalid_date_rows": invalid_date_rows,
        "invalid_age_rows": invalid_age_rows,
        "is_fresh": bool(
            total_rows > 0
            and invalid_date_rows == 0
            and invalid_age_rows == 0
            and stale_ratio <= MAX_STALE_RATIO
        ),
    }
    write_json(Path(report_path), payload)
    return payload


def _date_string(value: Any) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()
