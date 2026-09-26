from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import read_json
from ingestion.corruption import corrupt_clean_dataframe
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report


PROJECT_DIR = Path(__file__).resolve().parents[1]


def _settings(tmp_path: Path):
    settings = load_settings(PROJECT_DIR)
    paths = replace(
        settings.paths,
        quality_dir=tmp_path / "quality",
        gx_dir=tmp_path / "quality" / "gx",
    )
    return replace(settings, paths=paths)


def _clean_df() -> pd.DataFrame:
    return pd.read_json(PROJECT_DIR / "data" / "clean" / "papers_clean.json")


def test_corruption_suite_is_deterministic_and_logs_all_six_scenarios(tmp_path):
    source = _clean_df()
    log_path = tmp_path / "corruption_log.json"

    first = corrupt_clean_dataframe(source, log_path)
    second = corrupt_clean_dataframe(source, log_path)
    log = read_json(log_path)

    assert first.equals(second)
    assert source["paper_id"].is_unique
    assert first["paper_id"].duplicated().any()
    assert (first["title"].str.len() < 8).any()
    assert (first["summary"].str.len() < 20).any()
    assert (first["age_days"] > 180).mean() > 0.25
    assert log["scenario_count"] == 6
    assert {item["scenario"] for item in log["scenarios"]} == {
        "drop_latest_records",
        "blank_summary",
        "inject_noise",
        "truncate_title",
        "stale_date",
        "duplicate_rows",
    }


def test_freshness_sla_detects_corruption_and_accepts_clean_data(tmp_path):
    settings = _settings(tmp_path)
    clean = _clean_df()
    corrupted = corrupt_clean_dataframe(clean, tmp_path / "corruption_log.json")

    clean_report = build_freshness_report(clean, settings, tmp_path / "clean_freshness.json")
    bad_report = build_freshness_report(
        corrupted, settings, tmp_path / "corrupted_freshness.json"
    )

    assert clean_report["is_fresh"] is True
    assert clean_report["stale_ratio"] <= 0.25
    assert bad_report["is_fresh"] is False
    assert bad_report["stale_ratio"] > 0.25


def test_gx_quality_gate_passes_clean_and_rejects_corrupted_data(tmp_path):
    settings = _settings(tmp_path)
    clean = _clean_df()
    corrupted = corrupt_clean_dataframe(clean, tmp_path / "corruption_log.json")

    clean_result = run_data_quality_checks(clean, settings, "clean_test")
    bad_result = run_data_quality_checks(corrupted, settings, "corrupted_test")

    assert clean_result["success"] is True
    assert clean_result["statistics"]["evaluated_expectations"] == 5
    assert bad_result["success"] is False
    assert bad_result["statistics"]["unsuccessful_expectations"] >= 2


def test_comparison_report_has_three_states_and_computed_deltas(tmp_path):
    output = tmp_path / "comparison.md"
    baseline = {"samples": 10, "retrieval_hit_rate": 1.0, "mean_token_f1": 1.0,
                "judge_accuracy": 1.0, "mean_judge_score": 5.0}
    corrupted = {"samples": 10, "retrieval_hit_rate": 0.3, "mean_token_f1": 0.2,
                 "judge_accuracy": 0.3, "mean_judge_score": 2.0}
    repaired = dict(baseline)
    quality_bad = {"success": False, "statistics": {"successful_expectations": 2,
                                                      "evaluated_expectations": 5}}
    quality_good = {"success": True, "statistics": {"successful_expectations": 5,
                                                      "evaluated_expectations": 5}}
    freshness_bad = {"is_fresh": False, "stale_rows": 8, "total_rows": 20,
                     "stale_ratio": 0.4}
    freshness_good = {"is_fresh": True, "stale_rows": 0, "total_rows": 24,
                      "stale_ratio": 0.0}

    generate_corruption_report(
        output, baseline, corrupted, repaired, quality_bad, quality_good,
        freshness_bad, freshness_good,
    )

    report = output.read_text(encoding="utf-8")
    assert "Baseline vs Corrupted vs Repaired" in report
    assert "-0.7000" in report
    assert "Idempotent Repair" in report
