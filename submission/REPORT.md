# Báo cáo Day 13 Observability

## 1. Thông tin nhóm

- Tên nhóm:
- Repository URL:
- Commit SHA cuối:
- Thành viên và vai trò:

## 2. Kết quả kỹ thuật

- Điểm baseline `validate_logs.py`: **30/100**
  - Tổng số log records đã phân tích: 19
  - Records thiếu trường bắt buộc: 19
  - Records thiếu enrichment (`context`): 19
  - Số correlation ID duy nhất: 0
  - PII leak tiềm ẩn: 0
  - Kết quả: **FAILED** required fields, correlation ID propagation và log enrichment; **PASSED** PII scrubbing.
- Điểm `validate_logs.py` sau khi hoàn thiện CP1: 100/100 — 24 bản ghi hợp lệ, 13 correlation ID duy nhất, 0 bản ghi thiếu enrichment, 0 PII leak
- Tổng số traces:
- Số PII leak còn lại:
- Link/đường dẫn dashboard:

## 3. Logging và tracing

- Evidence log validator: [Kết quả validator CP1 đạt 100/100](evidence/cp1-validator.png)
- Evidence correlation ID: [Log có Correlation ID và metadata](evidence/cp1-correlation-redacted-log.png)
- Evidence PII redaction: [Log có email đã được che](evidence/cp1-correlation-redacted-log.png)
- Evidence trace waterfall:
- Giải thích một span đáng chú ý:

## 4. Prompt versioning

- Prompt name:
- Version/label baseline:
- Version/label candidate:
- Trace ID của mỗi version:
- Bằng chứng đổi label hoặc rollback:

## 5. Dashboard, SLO và alerts

- Kết quả `validate_dashboard.py`:
- Evidence dashboard:
- SLO đã chọn và lý do:
- Alert rules và runbook:

## 6. Điều tra challenge

- Challenge ID:
- Triệu chứng từ metrics:
- Trace ID liên quan:
- Log line/correlation ID liên quan:
- Root cause:
- Fix action:
- Preventive measure:

## 7. Đóng góp cá nhân

Với mỗi thành viên, ghi rõ nhiệm vụ và link commit/PR tương ứng.

| Thành viên | Phần việc | Commit/PR | Điều đã học |
|---|---|---|---|
| Đào Nhật Anh – 01464 | Triển khai Correlation ID middleware, response timing, log-context enrichment; giữ `x-request-id` khi HTTP 500 và cập nhật load test | `35a40c7` | Hiểu cách dùng contextvars để truy vết request và lý do phải xóa context cũ nhằm tránh rò rỉ metadata giữa các request |
