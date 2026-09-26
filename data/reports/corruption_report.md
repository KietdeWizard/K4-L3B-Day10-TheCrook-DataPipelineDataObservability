# Data Corruption, Detection and Idempotent Repair

All three evaluations use the same 10-question test set, embedding model and retrieval configuration.

## Baseline vs Corrupted vs Repaired

| Metric | Baseline | Corrupted | Repaired | Corruption Δ vs baseline | Repair Δ vs baseline |
|---|---:|---:|---:|---:|---:|
| Samples | 10 | 10 | 10 | +0.0000 | +0.0000 |
| Retrieval hit rate | 1.0000 | 0.4000 | 1.0000 | -0.6000 | +0.0000 |
| Mean token F1 | 1.0000 | 0.4814 | 1.0000 | -0.5186 | +0.0000 |
| Judge accuracy | 1.0000 | 0.5000 | 1.0000 | -0.5000 | +0.0000 |
| Mean judge score | 5 | 2.6000 | 5 | -2.4000 | +0.0000 |

## Observability signals

| State | GX quality gate | Successful checks | Freshness SLA | Stale rows | Stale ratio |
|---|---|---:|---|---:|---:|
| Baseline | See `baseline_quality_report.json` | — | See `freshness_report.json` | — | — |
| Corrupted | **FAIL** | 3/5 | **FAIL** | 12/23 | 52.17% |
| Repaired | **PASS** | 5/5 | **PASS** | 1/24 | 4.17% |

## Impact analysis

- Corruption changed retrieval hit rate by **-0.6000** from baseline and triggered the observable quality/freshness signals above.
- Repair recovered **+0.6000** retrieval-hit-rate points from the corrupted state.
- Repaired retrieval differs from baseline by **+0.0000**; a value near zero demonstrates reproducible restoration from the raw snapshot.
- The repair is idempotent because it rebuilds clean data and its vector collection from preserved raw records instead of mutating corrupted rows in place.
