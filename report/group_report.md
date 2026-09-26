# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
|---|---|
| Khóa/Lớp | K4-L3B-DAY10 |
| Tên nhóm | TheCrook |
| Repository | https://github.com/KietdeWizard/K4-L3B-Day10-TheCrook-DataPipelineDataObservability |
| Ngày hoàn thành | 2026-09-26 |

| STT | Họ và tên | MSSV | Vai trò | Deliverable chính |
|---:|---|---|---|---|
| 1 | Nguyễn Minh Kiệt | 2A202602373 | Data Foundation Owner | ingestion, cleaning, test set, baseline pipeline |
| 2 | Đào Minh Hiếu | 2A202602561 | Completion & Integration Owner | observability, corruption, repair, reporting |

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành pipeline RAG từ snapshot Crossref đến cleaning, embedding MiniLM, ChromaDB, benchmark 10 câu hỏi, đánh giá và observability. Baseline có 24 records, vượt 6/6 Great Expectations checks, stale ratio 4.17%, retrieval hit rate 1.0 và mean token F1 1.0. Suite deterministic tiêm đủ sáu lỗi. Dữ liệu corrupted chỉ đạt 4/6 checks, stale ratio tăng lên 52.17%, hit rate giảm còn 0.4 và token F1 còn 0.4814. Repair rebuild từ raw snapshot bất biến, khôi phục 24 records, 6/6 checks, freshness 4.17% và toàn bộ metrics baseline. Hai entrypoint và 4 automated tests đều chạy exit code 0 với provider `mock`. Ragas là optional pass và không bật trong lần xác minh này.

## 3. Kiến trúc và ownership

```text
Crossref snapshot -> raw records -> clean dataframe
  -> MiniLM + ChromaDB -> shared test set -> baseline evaluation
  -> six corruptions -> re-index/evaluate -> rebuild from raw -> verify recovery
```

| Khối | Xử lý | Output | Owner |
|---|---|---|---|
| Ingestion/cleaning | Parse, fallback, JATS cleanup, deduplicate, `age_days` | `data/raw/`, `data/clean/` | Kiệt |
| Evaluation/index | 10 questions, MiniLM, ChromaDB, mock QA | `data/eval/`, `data/embeddings/`, `data/chroma/` | Kiệt |
| Observability | GX 1.x checks, freshness SLA | `data/quality/` | Hiếu |
| Corruption/repair | Six corruptions, raw-snapshot rebuild, reports | `data/results/`, `data/reports/` | Hiếu |

## 4. Cách tái hiện

```bash
python -m pip install -e ".[dev]"
python script/run_phase1.py
python script/run_corruption_flow.py
python -m pytest -q
```

Lần xác minh cuối dùng `LLM_PROVIDER=mock`, model `sentence-transformers/all-MiniLM-L6-v2`, 24 records, `top_k=4`, freshness threshold 180 ngày và max stale ratio 25%. `REFRESH_SOURCE=false` giữ snapshot offline. Cùng `data/eval/test_set.json` được dùng cho cả ba trạng thái.

| Lệnh | Trạng thái | Bằng chứng |
|---|---|---|
| `python script/run_phase1.py` | PASS | 24 records; Hit Rate 1.0; F1 1.0 |
| `python script/run_corruption_flow.py` | PASS | Sinh lại bảng so sánh ba trạng thái |
| `python -m pytest -q` | PASS | 4 passed |

## 5. Data contract và evaluation

Nguồn là Crossref Works API với query `agentic retrieval augmented generation large language model`; pipeline mặc định dùng snapshot đã lưu. Request online retry ba lần với exponential backoff cho 429/5xx. Clean schema giữ identity, text, author/category, dates, URLs, `age_days` và `text_for_embedding`. Record thiếu identity/title bị loại; DOI được deduplicate. Embedding text ghép title, summary, authors, categories và published date.

Benchmark gồm 10 câu thuộc bốn loại `summary`, `authors`, `date`, `categories`. Ground truth lưu DOI, retrieval dùng `top_k=4`, và mọi trạng thái dùng cùng test set để so sánh công bằng.

## 6. Observability và corruption

GX 1.23.2 chạy 6 expectations: row count 5–5000; not-null cho `paper_id`, `title`, `text_for_embedding`; unique `paper_id`; summary length 30–20000. Freshness fail khi tỷ lệ `age_days > 180` vượt 25%.

| Trạng thái | Rows | GX | Stale ratio | Freshness |
|---|---:|---:|---:|---|
| Baseline | 24 | PASS 6/6 | 4.17% | PASS |
| Corrupted | 23 | FAIL 4/6 | 52.17% | FAIL |
| Repaired | 24 | PASS 6/6 | 4.17% | PASS |

| Corruption | Rows | Tác động chính |
|---|---:|---|
| Drop latest records | 5 | Mất ground-truth documents mới |
| Blank summary | 6 | Vi phạm summary length |
| Inject noise | 10 | Làm sai lệch embedding/context |
| Truncate title | 6 | Phá title matching |
| Stale date | 8 | Đẩy stale ratio vượt SLA |
| Duplicate rows | 4 | Vi phạm uniqueness |

`corruption_log.json` ghi scenario, mô tả, số row và DOI bị tác động. Repair rebuild dataframe và index từ `crossref_records.json`, nên idempotent và không phụ thuộc việc đảo ngược từng corruption.

## 7. Tác động và phục hồi

| Metric | Baseline | Corrupted | Repaired | Kết luận |
|---|---:|---:|---:|---|
| Retrieval hit rate | 1.0000 | 0.4000 | 1.0000 | Giảm 60%, phục hồi hoàn toàn |
| Mean token F1 | 1.0000 | 0.4814 | 1.0000 | Giảm 51.86%, phục hồi hoàn toàn |
| Judge accuracy | 1.0000 | 0.5000 | 1.0000 | Giảm 50%, phục hồi hoàn toàn |
| Mean judge score | 5.0000 | 2.6000 | 5.0000 | Giảm 2.4 điểm, phục hồi hoàn toàn |
| Quality | PASS 6/6 | FAIL 4/6 | PASS 6/6 | Phát hiện duplicate/summary faults |
| Freshness | PASS | FAIL | PASS | Phát hiện stale-date corruption |

Chuỗi bằng chứng: corruption làm GX và freshness cùng fail, đồng thời Hit Rate/F1 suy giảm; rebuild từ lineage anchor làm quality signals và agent metrics trở lại baseline.

## 8. Giới hạn và checklist

- Kết quả QA dùng mock provider để tái lập và không phụ thuộc API key; production LLM cần đánh giá riêng.
- Ragas chưa bật trong lần chạy này.
- Suite deterministic phục vụ regression testing, không mô phỏng hết drift thực tế.

- [x] Thông tin nhóm, repository và phân công đã hoàn thiện.
- [x] Hai pipeline và test suite đã chạy lại exit code 0.
- [x] Ba trạng thái dùng chung evaluation set.
- [x] Metrics và kết luận khớp artifacts được sinh tự động.
- [x] Cả hai thành viên có báo cáo cá nhân.
- [x] `.env` không được track; source/report không chứa secret.
