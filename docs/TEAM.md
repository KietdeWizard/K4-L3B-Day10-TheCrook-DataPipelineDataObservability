# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên nhóm:** `TheCrook`
- **Mã nhóm / Lớp:** `K4-L3B-DAY10`
- **Tên repository nộp bài:** `K4-L3B-DAY10-TheCrook-DataPipelineDataObservability`
- **Số lượng thành viên:** 2

---

## Thành viên và phân công

| STT | Họ và tên | MSSV | Email | Vai trò | Phạm vi phụ trách chính | Báo cáo cá nhân |
|---:|---|---|---|---|---|---|
| 1 | Nguyễn Minh Kiệt | `2A202602373` | Chưa cung cấp | Nhóm trưởng / Data Foundation Owner | Làm trước phần ingestion, cleaning, benchmark test set và baseline pipeline; bàn giao code cùng artifacts cho thành viên 2 | `report/2A202602373_NguyenMinhKiet.md` |
| 2 | Đào Minh Hiếu | `2A202602561` | `hdao13789@gmail.com` | Thành viên / Completion & Integration Owner | Nhận phần baseline từ thành viên 1, hoàn thiện observability, corruption/repair, chạy toàn tuyến và merge lên `main` | `report/2A202602561_DaoMinhHieu.md` |

---

## Phân công chi tiết

### Nguyễn Minh Kiệt — 2A202602373

- **Vai trò:** Nhóm trưởng, Data Foundation & Baseline Pipeline Owner; thực hiện giai đoạn đầu và bàn giao cho thành viên 2.
- **Module phụ trách:**
  - `src/ingestion/crossref.py`
  - `src/ingestion/cleaning.py`
  - `src/evaluation/testset.py`
  - `src/pipelines/phase1.py`
- **Nhiệm vụ:**
  - Hoàn thiện việc parse dữ liệu Crossref, retry và fallback từ snapshot offline.
  - Bảo toàn raw response và raw records phục vụ data lineage.
  - Chuẩn hóa dữ liệu, tính `age_days`, loại trùng và tạo `text_for_embedding`.
  - Sinh bộ benchmark gồm 10 câu hỏi thuộc bốn loại nghiệp vụ.
  - Tích hợp và chạy baseline pipeline end-to-end.
  - Commit phần việc lên branch cá nhân, ghi rõ lệnh kiểm chứng và bàn giao code/artifacts cho Đào Minh Hiếu.
  - Hỗ trợ xử lý lỗi contract dữ liệu nếu phát sinh trong giai đoạn tích hợp cuối.
- **Output bàn giao:**
  - `data/raw/crossref_response.json`
  - `data/raw/crossref_records.json`
  - `data/clean/papers_clean.csv`
  - `data/clean/papers_clean.json`
  - `data/eval/test_set.json`
  - `data/results/baseline_metrics.json`
  - `data/reports/phase1_report.md`

### Đào Minh Hiếu — 2A202602561

- **Vai trò:** Completion & Integration Owner; nhận kết quả giai đoạn đầu, hoàn thiện phần còn lại và chốt phiên bản nộp bài.
- **Module phụ trách:**
  - `src/observability/quality.py`
  - `src/observability/reporting.py`
  - `src/ingestion/corruption.py`
  - `src/pipelines/corruption_flow.py`
- **Nhiệm vụ:**
  - Thiết lập bốn expectations bắt buộc bằng Great Expectations 1.x.
  - Tính stale ratio và giám sát Freshness SLA theo ngưỡng 180 ngày/25%.
  - Sinh báo cáo quality, freshness và báo cáo Markdown từ artifact thực tế.
  - Triển khai sáu kịch bản data corruption và ghi corruption log.
  - Phục hồi idempotent từ raw snapshot, tái lập index và đánh giá lại.
  - Tạo bảng đối chiếu Baseline vs Corrupted vs Repaired.
  - Tích hợp branch của Nguyễn Minh Kiệt, giải quyết lỗi ghép nối giữa các module và chạy lại cả hai pipeline.
  - Kiểm tra báo cáo, metrics, Git status và merge phiên bản hoàn chỉnh lên `main`.
- **Output bàn giao:**
  - `data/quality/baseline_quality_report.json`
  - `data/quality/corrupted_quality_report.json`
  - `data/quality/freshness_report.json`
  - `data/results/corruption_log.json`
  - `data/results/corrupted_metrics.json`
  - `data/results/repaired_metrics.json`
  - `data/reports/corruption_report.md`

---

## Quy trình bàn giao và tích hợp

Nhóm thực hiện tuần tự theo quy trình sau:

1. Nguyễn Minh Kiệt hoàn thành ingestion, cleaning, test set và baseline pipeline trên branch cá nhân.
2. Nguyễn Minh Kiệt chạy kiểm tra Phase 1, commit phần việc và push branch để bàn giao cho Đào Minh Hiếu.
3. Đào Minh Hiếu nhận code baseline, kiểm tra input/output contract rồi hoàn thiện quality, freshness, reporting và corruption/repair flow.
4. Đào Minh Hiếu chạy lại `python script/run_phase1.py` và `python script/run_corruption_flow.py` trên phiên bản tích hợp.
5. Sau khi artifacts và metrics hợp lệ, Đào Minh Hiếu merge phiên bản hoàn chỉnh vào `main` và push lên GitHub.
6. Cả hai thành viên kiểm tra GitHub Contributors và tự nộp link repository trên VLearn.

Quy trình Git gợi ý:

```text
feature/kiet-baseline
        -> bàn giao cho Hiếu
        -> feature/hieu-observability-recovery
        -> kiểm tra toàn tuyến
        -> merge vào main
```

---

## Trách nhiệm chung

Cả hai thành viên cùng chịu trách nhiệm:

- Thống nhất raw schema, clean schema, document identity và artifact paths.
- Review phần bàn giao và xử lý các lỗi tích hợp trước khi merge vào `main`.
- Dùng cùng một `data/eval/test_set.json` cho baseline, corrupted và repaired.
- Chạy lại `python script/run_phase1.py` và `python script/run_corruption_flow.py` trước khi nộp.
- Đối chiếu số liệu trong báo cáo với các file metrics và quality artifacts thực tế.
- Hiểu và có khả năng giải thích toàn bộ luồng end-to-end khi live demo.
- Không commit `.env`, API key, token, cache hoặc dữ liệu bí mật.

---

## Tỷ lệ đóng góp dự kiến

| Thành viên | Tỷ lệ đóng góp | Phạm vi chính |
|---|---:|---|
| Nguyễn Minh Kiệt | 50% | Data foundation, benchmark, baseline pipeline và bàn giao Phase 1 |
| Đào Minh Hiếu | 50% | Hoàn thiện observability, corruption/recovery, tích hợp và merge `main` |
| **Tổng** | **100%** | |

> Tỷ lệ trên là phân công dự kiến và cần được cập nhật theo đóng góp thực tế trước khi nộp. Lịch sử commit trên GitHub phải phù hợp với phần việc khai báo của từng thành viên.
