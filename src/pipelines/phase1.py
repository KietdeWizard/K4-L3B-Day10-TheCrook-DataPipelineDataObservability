from __future__ import annotations

from typing import Any

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def run_phase1_pipeline(settings: Settings) -> dict[str, Any]:
    """Run the reproducible baseline pipeline and return its key artifacts."""
    records = fetch_source_records(settings)
    clean_df = build_clean_dataframe(records, now_utc())
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(
        clean_df,
        settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )

    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        test_set = build_test_set(clean_df, settings.paths.eval_testset)
    else:
        test_set = read_json(settings.paths.eval_testset)
        if not isinstance(test_set, list) or len(test_set) != 10:
            test_set = build_test_set(clean_df, settings.paths.eval_testset)

    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(
        clean_df,
        settings,
        settings.paths.freshness_report,
    )
    source_summary = {
        "source": settings.source_api,
        "query": settings.source_query,
        "raw_records": len(records),
        "clean_records": len(clean_df),
        "test_questions": len(test_set),
        "collection_name": index.collection_name,
        "embedding_model": settings.embedding_model,
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary,
        evaluation.summary,
        quality,
        freshness,
    )
    return {
        "source_summary": source_summary,
        "metrics": evaluation.summary,
        "quality": quality,
        "freshness": freshness,
        "report_path": str(settings.paths.baseline_report),
    }


def main() -> None:
    result = run_phase1_pipeline(load_settings())
    metrics = result["metrics"]
    print("Phase 1 pipeline completed.")
    print(f"Clean records: {result['source_summary']['clean_records']}")
    print(f"Retrieval hit rate: {metrics['retrieval_hit_rate']:.4f}")
    print(f"Mean token F1: {metrics['mean_token_f1']:.4f}")
    print(f"Report: {result['report_path']}")
