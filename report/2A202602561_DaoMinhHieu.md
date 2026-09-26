# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Đào Minh Hiếu |
| MSSV | `2A202602561` |
| Email | `hdao13789@gmail.com` |
| Khóa/Lớp | K4-L3B |
| Tên nhóm | TheCrook |
| Vai trò chính | Completion & Integration Owner |
| Repository | `https://github.com/KietdeWizard/K4-L3B-Day10-TheCrook-DataPipelineDataObservability` |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

| Module/deliverable | File/hàm phụ trách | Input | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Data quality gate | `src/observability/quality.py` | Clean/corrupted/repaired dataframe | GX 1.x quality reports | Hoàn thành, đã kiểm tra |
| Freshness SLA | `build_freshness_report` | `published`, `age_days` | Freshness reports 180 ngày/25% | Hoàn thành, đã kiểm tra |
| Báo cáo máy sinh | `src/observability/reporting.py` | Metrics, quality, freshness | Phase 1 và corruption Markdown reports | Hoàn thành, đã kiểm tra |
| Corruption suite | `src/ingestion/corruption.py` | Clean dataframe | Corrupted data và log 6 kịch bản | Hoàn thành, đã kiểm tra |
| Repair và tích hợp | `src/pipelines/corruption_flow.py` | Raw snapshot, cùng test set | 3 bộ metrics và repaired artifacts | Hoàn thành, đã chạy end-to-end |
| Automated tests | `tests/test_observability_and_recovery.py` | Các module trên | 4 kiểm thử tự động | 4/4 passed |

Ngoài phạm vi chính, tôi bổ sung bootstrap import cho hai script, lazy import các LLM/Ragas dependency tùy chọn và ưu tiên model embedding đã cache để pipeline chạy ổn định cả khi offline.

## 3. Kết quả theo vai trò

| Nhiệm vụ | Artifact/bằng chứng | Kết quả |
|---|---|---|
| GX quality gate baseline | `data/quality/baseline_quality_report.json` | PASS, 6/6 checks |
| Phát hiện dữ liệu bẩn | `data/quality/corrupted_quality_report.json` | FAIL, 3/5 checks; phát hiện duplicate ID và summary quá ngắn |
| Freshness corruption | `data/quality/corrupted_freshness_report.json` | FAIL, 12/23 stale rows, 52.17% |
| Sáu kịch bản corruption | `data/results/corruption_log.json` | Đủ 6/6 kịch bản, có danh sách DOI bị tác động |
| Phục hồi chất lượng | `data/quality/repaired_quality_report.json` | PASS, 6/6 checks |
| Phục hồi freshness | `data/quality/repaired_freshness_report.json` | PASS, 1/24 stale rows, 4.17% |
| So sánh ba trạng thái | `data/reports/corruption_report.md` | Baseline → Corrupted → Repaired bằng số liệu thực |

## 4. Giải thích phần kỹ thuật

### Data quality và freshness

Quality gate dùng đúng API Great Expectations 1.x với ephemeral context, pandas datasource, dataframe asset, whole-dataframe batch và các expectation bắt buộc: row count, not-null, unique và string length. `paper_id` được kiểm tra cả completeness lẫn uniqueness; `title` được kiểm tra not-null; `summary` phải dài từ 20 đến 20.000 ký tự.

Freshness là tín hiệu riêng: một dòng được coi là stale khi `age_days > 180`. Dataset chỉ đạt SLA khi tỷ lệ stale không vượt 25%, không có ngày hoặc tuổi dữ liệu không hợp lệ, và dataset không rỗng.

### Corruption và repair

Corruption suite chạy xác định và gồm sáu lỗi: bỏ 20% bài mới nhất, xóa summary, chèn noise, cắt title dưới 8 ký tự, làm ngày cũ và thêm bản ghi trùng. Sau mỗi thay đổi, `summary_chars` và `text_for_embedding` được dựng lại để index thực sự nhận dữ liệu bẩn. Audit log ghi số lượng và DOI bị tác động của từng lỗi.

Repair không sửa ngược từng dòng corrupted. Pipeline đọc lại `data/raw/crossref_records.json`, gọi cùng cleaning contract, dựng lại collection `papers-repaired`, rồi đánh giá bằng chính `data/eval/test_set.json`. Cách rebuild từ lineage anchor khiến kết quả idempotent và tránh giữ ghost vectors.

### Input/output contract

| Thành phần | Mô tả |
|---|---|
| Input | 24 clean records, raw normalized snapshot, test set 10 câu |
| Corrupted output | 23 dòng sau drop/duplicate, 6 sự kiện corruption |
| Repaired output | 24 dòng, DOI unique, clean text/index được dựng lại |
| Metrics | Hit Rate, Token F1, judge accuracy, mean judge score |
| Điều kiện lỗi | Thiếu cột contract, dataset dưới 6 dòng, invalid date/age, missing raw snapshot |

## 5. Quyết định kỹ thuật quan trọng

- **Bối cảnh:** đảo ngược sáu phép corruption tại chỗ dễ bỏ sót lỗi, duplicate hoặc vector cũ.
- **Phương án cân nhắc:** viết hàm undo cho từng lỗi; hoặc rebuild từ raw snapshot đáng tin cậy.
- **Phương án chọn:** rebuild toàn bộ clean data và collection từ raw snapshot.
- **Lý do:** đơn giản hơn để chứng minh correctness, có data lineage rõ, và đảm bảo cùng input tạo cùng repaired output.
- **Bằng chứng:** chạy corruption flow lần thứ hai cho SHA-256 của repaired JSON và repaired metrics không đổi; repaired metrics khớp baseline.

## 6. Lỗi/blocker đã xử lý

- **Triệu chứng:** `python script/run_corruption_flow.py` chờ nhiều lần khi thư viện kiểm tra file model trên Hugging Face dù MiniLM đã được tải.
- **Nguyên nhân gốc:** `SentenceTransformer(model_name)` ưu tiên truy vấn remote metadata ở mỗi process mới.
- **Cách xử lý:** loader thử `local_files_only=True` trước, chỉ fallback sang tải mạng khi cache chưa có; đồng thời cache instance bằng `lru_cache`.
- **Xác minh:** sau lần tải đầu, corruption flow chạy offline exit code 0 trong khoảng 20 giây.
- **Điều học được:** reproducibility không chỉ phụ thuộc data snapshot mà còn phụ thuộc cách quản lý model artifact và optional dependency.

## 7. Hiểu biết luồng end-to-end

1. Crossref response được lưu nguyên bản, parse thành normalized records, cleaning thành dataframe, ghép năm phần của `text_for_embedding`, embed bằng MiniLM và nạp vào ChromaDB.
2. Mỗi câu trong test set giữ DOI ground truth. Retrieval hit kiểm tra DOI đó có trong top-k; câu trả lời được so với ground truth bằng Token F1 và judge.
3. Quality checks phát hiện vi phạm schema/completeness/uniqueness/length; freshness đo độ cũ theo SLA thời gian. Một dataset có thể hợp schema nhưng vẫn stale.
4. Ba trạng thái phải dùng cùng test set, embedding model và top-k để chênh lệch metric đến từ dữ liệu, không phải từ cấu hình thí nghiệm.
5. Repair thành công khi GX và freshness trở lại PASS, metrics trở lại baseline, clean data không duplicate, và lần chạy lặp lại cho cùng repaired artifact.

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
|---|---:|---:|---:|---|
| `retrieval_hit_rate` | 1.0000 | 0.4000 | 1.0000 | Giảm 0.6000 rồi phục hồi hoàn toàn |
| `mean_token_f1` | 1.0000 | 0.4814 | 1.0000 | Noise/drop/truncate làm câu trả lời sai rõ rệt |
| `judge_accuracy` | 1.0000 | 0.5000 | 1.0000 | Giảm một nửa rồi phục hồi |
| `mean_judge_score` | 5.0000 | 2.6000 | 5.0000 | Chất lượng câu trả lời giảm 2.4 điểm |
| Quality checks | PASS 6/6 | FAIL 4/6 | PASS 6/6 | Phát hiện duplicate và summary rỗng |
| Freshness status | PASS 4.17% stale | FAIL 52.17% stale | PASS 4.17% stale | Vượt ngưỡng 25% ở trạng thái corrupted |

Chuỗi bằng chứng thứ nhất: drop/noise/truncate/duplicate/stale → GX và freshness cùng báo FAIL → Hit Rate giảm từ 1.0 xuống 0.4 và Token F1 giảm xuống 0.4814.

Chuỗi bằng chứng thứ hai: rebuild từ raw snapshot → GX 6/6 và freshness 4.17% stale → toàn bộ metrics repaired bằng baseline. Nhóm lỗi ảnh hưởng retrieval rõ nhất là drop latest kết hợp truncate title vì năm ground-truth mới nhất bị loại và exact-title lookup của các record còn lại bị phá vỡ.

## 9. Điều học được và hướng cải thiện

1. Raw snapshot là điểm neo lineage cần thiết cho self-healing có thể tái hiện.
2. Observability phải kết hợp quality và freshness; chỉ một nhóm tín hiệu không bao phủ đủ lỗi dữ liệu.
3. Corruption test có giá trị khi thay đổi thực sự đi vào embedding/index và được đo trên benchmark không đổi.

Nếu có thêm thời gian, tôi sẽ thêm CI chạy các unit test nhẹ và một integration profile dùng model cache để tránh tải model lại trên mỗi job.

## 10. Cam kết

- [x] Nội dung phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận đều có artifact hoặc metric để đối chiếu.
- [x] Tôi chỉ ghi thành công cho các lệnh đã chạy exit code 0.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo không sao chép nguyên văn báo cáo thành viên khác.

**Họ và tên:** Đào Minh Hiếu

**Ngày xác nhận:** 2026-09-26
