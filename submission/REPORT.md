# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm: K4-DAY13-2A202601124
- Repository URL: [github.com/thanhvinh0702/K4-DAY13-2A202601124](https://github.com/thanhvinh0702/K4-DAY13-2A202601124)
- Commit SHA cuối đã xác minh: [`8d6c8d707a04d2bbc2bd5ea51fcfc8f5e02b8374`](https://github.com/thanhvinh0702/K4-DAY13-2A202601124/commit/8d6c8d707a04d2bbc2bd5ea51fcfc8f5e02b8374) — cần cập nhật lại sau khi commit các thay đổi cuối.
- Thành viên và vai trò:
  - Hoàng Thành Vinh: tích hợp source, tracing RAG/LLM, điều tra challenge và hoàn thiện báo cáo.
  - Đào Nhật Anh: correlation ID middleware, response timing, log enrichment và evidence CP1.
  - Hồ Thúy Hằng: PII scrubbing và kiểm chứng dữ liệu nhạy cảm.
  - Ngô Thị Thảo Linh: CP2, SLO, alert rules và runbook.
  - Trần Minh Hiền: metrics error rate và ứng dụng dashboard 6 panel trên nhánh `origin/main`.

## 2. Kết quả kỹ thuật

- Điểm baseline `validate_logs.py`: **30/100**
  - Tổng số log records đã phân tích: 19
  - Records thiếu trường bắt buộc: 19
  - Records thiếu enrichment (`context`): 19
  - Số correlation ID duy nhất: 0
  - PII leak tiềm ẩn: 0
  - Kết quả: **FAILED** required fields, correlation ID propagation và log enrichment; **PASSED** PII scrubbing.
- Điểm `validate_logs.py` sau khi hoàn thiện CP1: 100/100 — 24 bản ghi hợp lệ, 13 correlation ID duy nhất, 0 bản ghi thiếu enrichment, 0 PII leak
- Điểm `validate_logs.py` khi kiểm tra cuối: **100/100** — 9 bản ghi JSON hợp lệ được phân tích, 5 correlation ID duy nhất, 0 bản ghi thiếu required fields/enrichment và 0 PII leak.
- Tổng số traces: **70** traces trên Langfuse tại thời điểm kiểm tra ngày 11/08/2026.
- Số PII leak còn lại: **0** theo `python scripts/validate_logs.py`.
- Link/đường dẫn dashboard: [Dashboard contract 6 panel](../config/dashboard.yaml); evidence runtime gồm [latency, traffic và errors](evidence/dashboard-1.png) cùng [cost, tokens và quality](evidence/dashboard-2.png).

## 3. Logging và tracing

- Evidence log validator: [Kết quả validator CP1 đạt 100/100](evidence/cp1-validator.png)
- Evidence correlation ID: [Log có Correlation ID và metadata](evidence/cp1-correlation-redacted-log.png)
- Evidence PII redaction: [Log có email đã được che](evidence/cp1-correlation-redacted-log.png)
- Evidence trace waterfall: [Ảnh trace RAG/LLM và correlation ID](evidence/image.png); [Langfuse trace `7ea651388c67ca038f627ab695552192`](https://cloud.langfuse.com/project/cmsoemc2e01p1ad0dcg4qp9c6/traces/7ea651388c67ca038f627ab695552192) (yêu cầu quyền truy cập project).
- Giải thích một span đáng chú ý: trace challenge dài **2.652 ms**, gồm `rag.retrieve` **2.500 ms** (`rag_slow=true`, `doc_count=1`) và `llm.generate` **150 ms** (`cost_spike=false`). RAG chiếm khoảng 94,3% tổng thời gian trace và là span gây vượt ngưỡng 2.000 ms.

## 4. Prompt versioning

- Prompt name: `day13-chat` (text prompt).
- Version/label baseline: version **1**, từng được phục vụ qua label `production`; trace xác nhận `prompt_source=langfuse`, `prompt_version=1` và `prompt_label=production`.
- Version/label candidate: version **2**, hiện được promote với labels `production` và `latest`; trace xác nhận `prompt_source=langfuse`, `prompt_version=2` và `prompt_label=production`.
- Trace ID của mỗi version: version 1: [`7ea651388c67ca038f627ab695552192`](https://cloud.langfuse.com/project/cmsoemc2e01p1ad0dcg4qp9c6/traces/7ea651388c67ca038f627ab695552192); version 2: [`86af0cf108846714080e5c1ed9ee6ec7`](https://cloud.langfuse.com/project/cmsoemc2e01p1ad0dcg4qp9c6/traces/86af0cf108846714080e5c1ed9ee6ec7).
- Bằng chứng đổi label hoặc rollback: [Prompt versioning và trace version 2](evidence/prompt-versioning.png). Evidence cho thấy prompt có version 1 và 2, label `production`/`latest` đang trỏ tới version 2; đối chiếu với trace version 1 từng dùng `production` chứng minh thao tác promote label từ version 1 sang version 2.

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`: **HỢP LỆ: 6/6 panel có trong dashboard contract** (latency, traffic, errors, cost, tokens và quality).
- Evidence dashboard: [Ảnh 1 — latency, traffic và error rate](evidence/dashboard-1.png); [Ảnh 2 — cost, tokens và quality](evidence/dashboard-2.png). Hai ảnh hiển thị đủ 6 panel, time range 60 phút, auto-refresh 30 giây, đơn vị và threshold theo [dashboard contract](../config/dashboard.yaml).
- SLO đã chọn và lý do: SLO chính là **99,5% cửa sổ 5 phút hợp lệ có p95 latency ≤ 3.000 ms**. p95 phản ánh tail latency tốt hơn average và gắn trực tiếp với trải nghiệm người dùng; các guardrail bổ sung gồm error rate ≤2%, daily cost ≤2,5 USD và quality average ≥0,75. Chi tiết tại [config/slo.yaml](../config/slo.yaml).
- Alert rules và runbook: `ChatHighErrorRate` (critical, >2% trong 5 phút), `ChatHighLatencyP95` (warning, >3.000 ms trong 10 phút), `DailyAICostBudgetRisk` (warning, >2 USD trong 15 phút) và `ChatQualityDegraded` (warning, <0,75 trong 30 phút). Cấu hình tại [config/alert_rules.yaml](../config/alert_rules.yaml), quy trình xử lý tại [docs/alerts.md](../docs/alerts.md).

## 6. Điều tra challenge

- Challenge ID: `day13-k4-observability-v1` (cohort K4, incident `rag_slow`, feature bị ảnh hưởng: `monitoring`, ngưỡng latency: 2.000 ms).
- Triệu chứng từ metrics: sau khi chạy 5 input challenge với concurrency 5, hệ thống ghi nhận `traffic=15`, p50/p95/p99 đều **2.651 ms**, vượt ngưỡng challenge 2.000 ms; không phát sinh lỗi (`error_breakdown={}`), quality trung bình 0,84. Ở phía client, cả 5 request mất khoảng **13.266–13.269 ms**, cho thấy các tác vụ blocking bị xử lý tuần tự khi tải đồng thời.
- Trace ID liên quan: [`7ea651388c67ca038f627ab695552192`](https://cloud.langfuse.com/project/cmsoemc2e01p1ad0dcg4qp9c6/traces/7ea651388c67ca038f627ab695552192), session `k4-challenge-s01`. Waterfall gồm parent generation `run` 2.652 ms, child span `rag.retrieve` 2.500 ms và child generation `llm.generate` 150 ms.
- Log line/correlation ID liên quan: `data/logs.jsonl`, event `response_sent`, correlation ID `req-29bc5491`, session `k4-challenge-s01`, feature `monitoring`, `latency_ms=2651`, model `claude-sonnet-4-5`, timestamp `2026-08-11T09:50:14.342538Z`. Validator sau challenge đạt **100/100**, có 5 correlation ID duy nhất và 0 PII leak.
- Root cause: incident chính thức `rag_slow` làm `rag.retrieve` gọi blocking `time.sleep(2.5)`. Cộng thêm khoảng 150 ms của `llm.generate`, latency nội bộ đạt khoảng 2.651 giây. Vì `LabAgent.run()` là luồng đồng bộ được gọi trực tiếp trong endpoint async, thao tác blocking giữ event loop và làm 5 request concurrent chờ tuần tự, khiến latency quan sát từ client tăng lên khoảng 13,27 giây.
- Fix action: mitigation ngay lập tức là tắt incident bằng `python scripts/inject_incident.py --disable` và chạy lại cùng input để xác nhận latency phục hồi. Với hệ thống thật, đặt timeout cho vector store, dùng cached/fallback retrieval và chuyển tác vụ blocking sang API async hoặc thread pool để không chặn event loop.
- Preventive measure: duy trì child span `rag.retrieve`/`llm.generate`, gắn correlation ID vào trace metadata, thêm cảnh báo riêng khi RAG duration hoặc request p95 vượt 2.000 ms, kiểm thử tải concurrent trong CI/staging, và áp dụng timeout, circuit breaker cùng fallback cho vector store.

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Đào Nhật Anh – 01464 | Triển khai Correlation ID middleware, response timing, log-context enrichment; giữ `x-request-id` khi HTTP 500 và cập nhật load test | `35a40c7` | Hiểu cách dùng contextvars để truy vết request và lý do phải xóa context cũ nhằm tránh rò rỉ metadata giữa các request |
| Hoàng Thành Vinh - 01124| Tích hợp các nhánh, enrich log, bọc trace cho RAG/LLM, gắn correlation ID vào Langfuse và điều tra challenge | `f420ce2`, `6342769`, `8d6c8d7` | Hiểu cách nối Metrics → Trace → Log và tác động của synchronous blocking lên concurrent request |
| Hồ Thúy Hằng - 01806 | Hoàn thiện PII scrubbing và regex kiểm tra dữ liệu nhạy cảm | `47e8195` | Hiểu PII phải được scrub trước khi render/ghi JSON log |
| Ngô Thị Thảo Linh - 01318 | Hoàn thiện CP2, SLO, alert rules và runbook | `f8add70` | Biết thiết kế SLI/SLO, threshold, duration, severity và owner cho alert |
| Trần Minh Hiền - 01300 | Xây dựng error-rate metric và dashboard app đủ 6 nhóm panel | `8e663dd` trên `origin/main` | Biết chuyển log JSONL thành dashboard latency, traffic, error, token/cost và quality |
