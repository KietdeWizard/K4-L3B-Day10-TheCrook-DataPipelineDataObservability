# Phase 1 — Baseline Pipeline Report

This report is generated from the pipeline artifacts; values are not entered manually.

## Source and index

| Field | Value |
|---|---|
| Source | Crossref REST API |
| Query | agentic retrieval augmented generation large language model |
| Raw Records | 24 |
| Clean Records | 24 |
| Test Questions | 10 |
| Collection Name | papers-baseline |
| Embedding Model | sentence-transformers/all-MiniLM-L6-v2 |

## Baseline evaluation

| Metric | Value |
|---|---:|
| Samples | 10 |
| Retrieval hit rate | 1.0000 |
| Mean token F1 | 1.0000 |
| Judge accuracy | 1.0000 |
| Mean judge score | 5 |

## Great Expectations quality gate

Overall status: **PASS**

Successful checks: **5/5**

| Expectation | Column | Status |
|---|---|---|
| expect_table_row_count_to_be_between | — | PASS |
| expect_column_values_to_not_be_null | paper_id | PASS |
| expect_column_values_to_be_unique | paper_id | PASS |
| expect_column_values_to_not_be_null | title | PASS |
| expect_column_value_lengths_to_be_between | summary | PASS |

## Freshness SLA

| Signal | Value |
|---|---:|
| Threshold | 180 days |
| Maximum stale ratio | 25.00% |
| Stale rows | 1/24 |
| Stale ratio | 4.17% |
| Latest publication | 2026-07-22 |
| Oldest publication | 2026-03-28 |
| SLA status | **PASS** |

## Interpretation

The baseline is ready for comparison when both the GX quality gate and freshness SLA pass. Retrieval and answer metrics above form the reference point for the corruption and repair experiment.
