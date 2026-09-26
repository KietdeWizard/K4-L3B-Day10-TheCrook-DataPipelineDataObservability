# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Nguyễn Minh Kiệt |
| MSSV | `2A202602373` |
| Khóa/Lớp | K4-L3B |
| Tên nhóm | TheCrook |
| Vai trò chính | Nhóm trưởng / Data Foundation & Baseline Pipeline Owner |
| Repository | `https://github.com/KietdeWizard/K4-L3B-Day10-TheCrook-DataPipelineDataObservability` |
| Ngày cập nhật | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

| Module/deliverable | File/hàm phụ trách | Input | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Crossref ingestion | `src/ingestion/crossref.py` | Crossref payload hoặc snapshot offline | Hai raw JSON artifacts, 24 `PaperRecord` | Hoàn thành và đã kiểm tra |
| Cleaning/data modeling | `src/ingestion/cleaning.py` — `build_clean_dataframe` | Danh sách `PaperRecord`, thời điểm chạy | Clean dataframe, CSV và JSON | Hoàn thành và đã kiểm tra |
| Evaluation set | `src/evaluation/testset.py` — `build_test_set` | Clean dataframe | `data/eval/test_set.json` gồm 10 câu | Hoàn thành và đã kiểm tra |
| Baseline orchestration | `src/pipelines/phase1.py` — `run_phase1_pipeline` | Settings và các module pipeline | Baseline artifacts, metrics và report | Đã triển khai; chờ module observability/reporting của thành viên 2 để chạy end-to-end |

Phần việc được bàn giao cho Đào Minh Hiếu là clean schema, evaluation-set contract và baseline orchestration. Hiếu tiếp tục hoàn thiện Great Expectations, freshness, reporting, corruption/repair và chạy tích hợp cuối.

## 3. Kết quả theo vai trò

| Nhiệm vụ | File/hàm/artifact | Kết quả | Cách xác minh |
|---|---|---|---|
| Parse và bảo toàn dữ liệu Crossref | `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | 24 raw items và 24 normalized records | Lệnh kiểm tra Bước 2 |
| Chuẩn hóa dữ liệu | `build_clean_dataframe` | 24 dòng, 24 `paper_id` duy nhất | Kiểm tra row count và `nunique()` |
| Tạo benchmark | `build_test_set` | 10 câu, ID duy nhất | Đọc `data/eval/test_set.json` |
| Phân bổ dạng câu hỏi | `data/eval/test_set.json` | summary=3, authors=3, date=2, categories=2 | Đếm `question_type` |
| Nối baseline pipeline | `run_phase1_pipeline` | Ingest → clean → index → test set → evaluate → quality/freshness → report | Compile thành công; end-to-end đang chờ module thành viên 2 |

Artifacts đã tạo và xác minh:

- `data/raw/crossref_response.json`
- `data/raw/crossref_records.json`
- `data/clean/papers_clean.csv`
- `data/clean/papers_clean.json`
- `data/eval/test_set.json`

## 4. Giải thích phần kỹ thuật

### Vấn đề cần giải quyết

Phần việc của tôi chuyển dữ liệu Crossref không ổn định về schema thành data contract xác định cho các bước embedding, evaluation và observability. Pipeline phải chạy được khi có mạng, nhưng cũng phải giữ khả năng tái hiện bằng raw snapshot khi Crossref lỗi hoặc rate-limit.

### Cách triển khai

Crossref payload được bóc tách thành `PaperRecord`. Abstract được bỏ JATS/HTML, tác giả được ghép từ `given` và `family`, ngày xuất bản được chuẩn hóa thành ISO, và DOI được giữ làm document identity xuyên suốt pipeline. Fetch hỗ trợ retry cho lỗi tạm thời và chỉ ghi đè raw snapshot sau khi nhận payload hợp lệ.

Cleaning chuẩn hóa whitespace, loại record thiếu khóa thiết yếu, parse ngày theo UTC, tính `age_days`, loại trùng theo `paper_id` và tạo văn bản embedding gồm Title, Authors, Published, Categories và Summary. Test set chọn xác định 10 tài liệu duy nhất và phân bổ câu hỏi 3/3/2/2 qua bốn loại nghiệp vụ.

### Input, output và contract

| Thành phần | Mô tả |
|---|---|
| Input | Crossref response có `message.items`, hoặc `crossref_records.json` |
| Raw output | `PaperRecord` gồm DOI, title, summary, authors, categories, dates và URLs |
| Clean output | DataFrame 24 dòng với `age_days`, helper columns và `text_for_embedding` |
| Evaluation output | 10 câu hỏi có ID, type, ground truth và DOI ground-truth |
| Module phụ thuộc | `core.config`, `core.utils`, pandas và requests |
| Module sử dụng output | Retrieval index, metrics, quality gate và corruption flow |
| Điều kiện lỗi | API offline/429/503, payload sai schema, DOI trùng, ngày không hợp lệ hoặc thiếu dữ liệu thiết yếu |

### Cách xác minh

```powershell
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
```

- Kết quả thực tế: `Tín hiệu hoàn thành: Đã tải 24 bài báo`.
- Offline fallback giả lập: `fallback_records=24`.
- Cleaning: `clean_rows=24`, `unique_ids=24`.
- Evaluation set: `test_questions=10` với phân bổ `3/3/2/2`.

## 5. Quyết định kỹ thuật quan trọng

- **Bối cảnh:** Crossref là nguồn sống nên response có thể lỗi hoặc thay đổi giữa các lần chạy.
- **Phương án cân nhắc:** luôn gọi API; hoặc ưu tiên snapshot và chỉ refresh khi được yêu cầu.
- **Phương án chọn:** mặc định dùng snapshot đã bảo toàn, chỉ gọi API khi `REFRESH_SOURCE` được bật; nếu request thất bại thì fallback về snapshot.
- **Lý do:** cách này giảm rate-limit, giữ khả năng tái hiện và tránh ghi đè dữ liệu tốt bằng response lỗi.
- **Bằng chứng:** parser và fallback đều trả về đúng 24 records từ snapshot hiện tại.

## 6. Lỗi hoặc blocker đã xử lý

- **Triệu chứng:** cơ chế bắt lỗi request ban đầu tham chiếu sai vị trí của `RequestException`.
- **Nguyên nhân:** exception thuộc `requests.exceptions`, không phải thuộc tính top-level cần sử dụng trực tiếp.
- **Cách xử lý:** import `RequestException` từ `requests.exceptions` và dùng nhất quán trong retry/fallback.
- **Xác minh:** giả lập request offline và nhận kết quả `fallback_records=24`.
- **Blocker còn lại:** máy làm việc hiện chưa có Python/.venv hoàn chỉnh; Phase 1 cũng chưa thể chạy end-to-end cho đến khi `quality.py` và `reporting.py` của thành viên 2 được hoàn thiện.

## 7. Hiểu biết về luồng end-to-end

1. Crossref response được lưu nguyên bản, parse thành `PaperRecord`, làm sạch thành dataframe, ghép `text_for_embedding`, sinh vector bằng MiniLM và nạp vào ChromaDB.
2. Mỗi câu benchmark giữ DOI trong `ground_truth_doc_ids`. Retrieval hit được tính khi DOI mong đợi xuất hiện trong danh sách tài liệu truy xuất; câu trả lời được so với ground truth bằng Token F1 và judge.
3. Quality checks kiểm tra cấu trúc/completeness/uniqueness/validity. Freshness monitoring đo tuổi dữ liệu và tỷ lệ record vượt SLA 180 ngày.
4. Cùng một test set phải được dùng cho baseline, corrupted và repaired để thay đổi metric phản ánh thay đổi dữ liệu, không phải thay đổi câu hỏi.
5. Repair thành công khi clean data, quality/freshness signal và các metric repaired trở lại gần hoặc bằng baseline, đồng thời không tạo duplicate khi chạy lại.

## 8. Phân tích kết quả

Các metrics dưới đây chưa được tạo vì phần observability/reporting và corruption flow thuộc thành viên 2 chưa hoàn thiện. Không điền số liệu giả trước khi pipeline thực tế chạy xong.

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
|---|---:|---:|---:|---|
| `retrieval_hit_rate` | N/A | N/A | N/A | Chờ chạy toàn tuyến |
| `mean_token_f1` | N/A | N/A | N/A | Chờ chạy toàn tuyến |
| `judge_accuracy` | N/A | N/A | N/A | Chờ chạy toàn tuyến |
| `mean_judge_score` | N/A | N/A | N/A | Chờ chạy toàn tuyến |
| Quality checks | N/A | N/A | N/A | Chờ module observability |
| Freshness status | N/A | N/A | N/A | Chờ module observability |

Sau khi Hiếu hoàn thiện phần còn lại, bảng này phải được cập nhật trực tiếp từ `baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json` và các quality artifacts.

## 9. Điều học được và hướng cải thiện

1. Raw snapshot là lineage anchor giúp pipeline tái hiện được và tránh phụ thuộc hoàn toàn vào API ngoài.
2. Data contract ổn định quan trọng hơn việc chỉ làm sạch chuỗi, vì mọi bước indexing, evaluation và repair đều phụ thuộc cùng document identity.
3. Evaluation chỉ so sánh được ba trạng thái khi giữ nguyên test set, cấu hình retrieval và cách tính metric.

Nếu có thêm thời gian, tôi sẽ bổ sung unit tests cho payload thiếu trường, ngày chỉ có năm/tháng, duplicate DOI và retry 429/503, sau đó đưa các test này vào CI.

## 10. Cam kết

- [x] Nội dung phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end và module phụ trách.
- [x] Các kết quả được ghi có artifact hoặc output kiểm chứng.
- [x] Không khai báo pipeline end-to-end thành công khi chưa chạy được.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo không sao chép nguyên văn báo cáo của thành viên khác.

**Họ và tên:** Nguyễn Minh Kiệt  
**Ngày xác nhận:** 2026-09-26
