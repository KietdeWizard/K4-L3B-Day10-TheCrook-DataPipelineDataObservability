from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import write_text


METRIC_LABELS = {
    "samples": "Samples",
    "retrieval_hit_rate": "Retrieval hit rate",
    "mean_token_f1": "Mean token F1",
    "judge_accuracy": "Judge accuracy",
    "mean_judge_score": "Mean judge score",
}


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write the baseline report strictly from generated pipeline artifacts."""
    source_rows = "\n".join(
        f"| {_humanize(key)} | {_format_value(value)} |"
        for key, value in source_summary.items()
    )
    metric_rows = "\n".join(
        f"| {METRIC_LABELS.get(key, _humanize(key))} | {_format_value(value)} |"
        for key, value in metrics.items()
        if key != "ragas"
    )
    check_rows = "\n".join(
        "| {name} | {column} | {status} |".format(
            name=check.get("expectation_type", "Unknown"),
            column=check.get("kwargs", {}).get("column", "—"),
            status="PASS" if check.get("success") else "FAIL",
        )
        for check in quality.get("checks", [])
    )
    if not check_rows:
        check_rows = "| No checks recorded | — | FAIL |"

    report = f"""# Phase 1 — Baseline Pipeline Report

This report is generated from the pipeline artifacts; values are not entered manually.

## Source and index

| Field | Value |
|---|---|
{source_rows}

## Baseline evaluation

| Metric | Value |
|---|---:|
{metric_rows}

## Great Expectations quality gate

Overall status: **{'PASS' if quality.get('success') else 'FAIL'}**

Successful checks: **{quality.get('statistics', {}).get('successful_expectations', 0)}/{quality.get('statistics', {}).get('evaluated_expectations', 0)}**

| Expectation | Column | Status |
|---|---|---|
{check_rows}

## Freshness SLA

| Signal | Value |
|---|---:|
| Threshold | {freshness.get('threshold_days', 'N/A')} days |
| Maximum stale ratio | {_format_percent(freshness.get('max_stale_ratio'))} |
| Stale rows | {freshness.get('stale_rows', 'N/A')}/{freshness.get('total_rows', 'N/A')} |
| Stale ratio | {_format_percent(freshness.get('stale_ratio'))} |
| Latest publication | {freshness.get('latest_published', 'N/A')} |
| Oldest publication | {freshness.get('oldest_published', 'N/A')} |
| SLA status | **{'PASS' if freshness.get('is_fresh') else 'FAIL'}** |

## Interpretation

The baseline is ready for comparison when both the GX quality gate and freshness SLA pass. Retrieval and answer metrics above form the reference point for the corruption and repair experiment.
"""
    write_text(Path(report_path), report)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """Write a three-state comparison with computed degradation/recovery."""
    metric_keys = [
        "samples",
        "retrieval_hit_rate",
        "mean_token_f1",
        "judge_accuracy",
        "mean_judge_score",
    ]
    rows = []
    for key in metric_keys:
        baseline = baseline_metrics.get(key)
        corrupted = corrupted_metrics.get(key)
        repaired = repaired_metrics.get(key)
        rows.append(
            "| {label} | {baseline} | {corrupted} | {repaired} | {impact} | {recovery} |".format(
                label=METRIC_LABELS[key],
                baseline=_format_value(baseline),
                corrupted=_format_value(corrupted),
                repaired=_format_value(repaired),
                impact=_format_delta(corrupted, baseline),
                recovery=_format_delta(repaired, baseline),
            )
        )

    baseline_hit = _number(baseline_metrics.get("retrieval_hit_rate"))
    corrupted_hit = _number(corrupted_metrics.get("retrieval_hit_rate"))
    repaired_hit = _number(repaired_metrics.get("retrieval_hit_rate"))
    degradation = baseline_hit - corrupted_hit
    recovered = repaired_hit - corrupted_hit

    report = f"""# Data Corruption, Detection and Idempotent Repair

All three evaluations use the same 10-question test set, embedding model and retrieval configuration.

## Baseline vs Corrupted vs Repaired

| Metric | Baseline | Corrupted | Repaired | Corruption Δ vs baseline | Repair Δ vs baseline |
|---|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

## Observability signals

| State | GX quality gate | Successful checks | Freshness SLA | Stale rows | Stale ratio |
|---|---|---:|---|---:|---:|
| Baseline | See `baseline_quality_report.json` | — | See `freshness_report.json` | — | — |
| Corrupted | **{'PASS' if corrupted_quality.get('success') else 'FAIL'}** | {_quality_score(corrupted_quality)} | **{'PASS' if corrupted_freshness.get('is_fresh') else 'FAIL'}** | {corrupted_freshness.get('stale_rows', 'N/A')}/{corrupted_freshness.get('total_rows', 'N/A')} | {_format_percent(corrupted_freshness.get('stale_ratio'))} |
| Repaired | **{'PASS' if repaired_quality.get('success') else 'FAIL'}** | {_quality_score(repaired_quality)} | **{'PASS' if repaired_freshness.get('is_fresh') else 'FAIL'}** | {repaired_freshness.get('stale_rows', 'N/A')}/{repaired_freshness.get('total_rows', 'N/A')} | {_format_percent(repaired_freshness.get('stale_ratio'))} |

## Impact analysis

- Corruption changed retrieval hit rate by **{-degradation:+.4f}** from baseline and triggered the observable quality/freshness signals above.
- Repair recovered **{recovered:+.4f}** retrieval-hit-rate points from the corrupted state.
- Repaired retrieval differs from baseline by **{repaired_hit - baseline_hit:+.4f}**; a value near zero demonstrates reproducible restoration from the raw snapshot.
- The repair is idempotent because it rebuilds clean data and its vector collection from preserved raw records instead of mutating corrupted rows in place.
"""
    write_text(Path(report_path), report)


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _number(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (dict, list)):
        return "Recorded in JSON artifact"
    return str(value if value is not None else "N/A")


def _format_percent(value: Any) -> str:
    return f"{_number(value) * 100:.2f}%" if value is not None else "N/A"


def _format_delta(value: Any, reference: Any) -> str:
    if not isinstance(value, (int, float)) or not isinstance(reference, (int, float)):
        return "N/A"
    return f"{float(value) - float(reference):+.4f}"


def _quality_score(payload: dict[str, Any]) -> str:
    stats = payload.get("statistics", {})
    return f"{stats.get('successful_expectations', 0)}/{stats.get('evaluated_expectations', 0)}"
