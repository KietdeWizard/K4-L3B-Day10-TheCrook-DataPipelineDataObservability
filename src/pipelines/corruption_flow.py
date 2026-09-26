from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from pipelines.phase1 import run_phase1_pipeline
from retrieval.index import LocalEmbeddingIndex


def repair_from_raw_snapshot(settings: Settings) -> pd.DataFrame:
    """Rebuild clean data from the immutable raw-record lineage anchor."""
    raw_records = load_raw_records(settings.paths.raw_records_json)
    return build_clean_dataframe(raw_records, now_utc())


def run_corruption_flow_pipeline(settings: Settings) -> dict[str, Any]:
    """Evaluate deterministic corruption and idempotent raw-snapshot repair."""
    baseline_required = [
        settings.paths.clean_json,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_quality_report,
        settings.paths.freshness_report,
    ]
    if not all(path.exists() for path in baseline_required):
        run_phase1_pipeline(settings)

    baseline_metrics = read_json(settings.paths.baseline_metrics)
    clean_df = pd.DataFrame(read_json(settings.paths.clean_json))

    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    corrupted_evaluation = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings,
        settings.paths.quality_dir / "corrupted_freshness_report.json",
    )

    # Repair is a clean rebuild from the immutable lineage anchor, never an
    # in-place attempt to reverse individual corruptions.
    repaired_df = repair_from_raw_snapshot(settings)
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired_df.to_dict(orient="records"))
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    repaired_evaluation = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df,
        settings,
        settings.paths.quality_dir / "repaired_freshness_report.json",
    )

    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics,
        corrupted_evaluation.summary,
        repaired_evaluation.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
    )
    return {
        "baseline_metrics": baseline_metrics,
        "corrupted_metrics": corrupted_evaluation.summary,
        "repaired_metrics": repaired_evaluation.summary,
        "corrupted_quality": corrupted_quality,
        "repaired_quality": repaired_quality,
        "corrupted_freshness": corrupted_freshness,
        "repaired_freshness": repaired_freshness,
        "report_path": str(settings.paths.comparison_report),
    }


# Backward-compatible alias for the first integration draft.
run_corruption_pipeline = run_corruption_flow_pipeline


def main() -> None:
    result = run_corruption_flow_pipeline(load_settings())
    print("Corruption and repair pipeline completed.")
    print("State       Retrieval hit rate  Mean token F1")
    for label, key in (
        ("Baseline", "baseline_metrics"),
        ("Corrupted", "corrupted_metrics"),
        ("Repaired", "repaired_metrics"),
    ):
        metrics = result[key]
        print(
            f"{label:<11} {metrics['retrieval_hit_rate']:<19.4f} "
            f"{metrics['mean_token_f1']:.4f}"
        )
    print(f"Report: {result['report_path']}")
