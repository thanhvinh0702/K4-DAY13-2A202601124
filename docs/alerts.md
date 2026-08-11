# Alert runbook — Day 13 AI Observability

Owner chính: `sre-alerts`. Mọi lần xử lý phải lưu timestamp, cửa sổ dashboard, giá trị SLI, trace ID và correlation ID/log line dùng làm bằng chứng. Không ghi API key hoặc PII vào ticket.

Quy trình chung:

1. Acknowledge alert, ghi thời điểm bắt đầu và kiểm tra alert có đủ mẫu (`minimum_requests`/`minimum_responses`).
2. Mở đúng panel trong 60 phút gần nhất, so sánh thời điểm vượt threshold với traffic và các SLI còn lại.
3. Từ khoảng thời gian bất thường, mở trace đại diện; dùng correlation ID của trace để tìm log tương ứng và xác nhận nguyên nhân.
4. Mitigate trước, sửa lâu dài sau. Chỉ đóng alert khi điều kiện đã dưới ngưỡng liên tục một khoảng bằng `duration`.

## ChatHighErrorRate

- Severity: `critical`; SLO: `error_rate_pct <= 2%`; duy trì: 5 phút, tối thiểu 10 request.
- Ảnh hưởng: người dùng không nhận được câu trả lời hoặc API trả lỗi.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Error rate and breakdown**, xác nhận tỷ lệ >2%, volume và `error_type` phổ biến nhất.
  2. Mở các trace lỗi trong cùng khoảng thời gian, xác định bước đầu tiên có trạng thái lỗi và ghi lại trace ID.
  3. Tìm `request_failed` theo correlation ID trong log; kiểm tra error type, feature, model và incident state mà không sao chép payload nhạy cảm.
- Mitigation tạm thời: tắt incident/feature gây lỗi nếu đã được xác nhận; chuyển sang đường fallback an toàn; rollback thay đổi gần nhất nếu có bằng chứng thời gian khớp.
- Escalation: primary on-call xử lý ngay; báo application owner nếu chưa xác định được nguyên nhân trong 10 phút.
- Điều kiện đóng: error rate <=2% liên tục 5 phút và có ít nhất 10 request xác nhận.

## ChatHighLatencyP95

- Severity: `warning`; SLO: `p95 <= 3000 ms`; duy trì: 10 phút, tối thiểu 10 request.
- Ảnh hưởng: ít nhất 5% request thành công phản hồi chậm, làm trải nghiệm chat bị gián đoạn.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Latency percentiles**, xác nhận p95 >3000 ms và kiểm tra traffic có đủ mẫu.
  2. Chọn trace chậm trong cửa sổ cảnh báo, so sánh duration các span để khoanh vùng bước chiếm thời gian.
  3. Dùng correlation ID tìm log, đối chiếu `latency_ms`, feature/model và các error lân cận để chứng minh root cause.
- Mitigation tạm thời: bật fallback/cached response cho bước chậm đã xác nhận; giảm concurrency hoặc rollback thay đổi gây regression nếu phù hợp.
- Escalation: báo application owner khi kéo dài 20 phút hoặc p95 >6000 ms trong 5 phút.
- Điều kiện đóng: p95 <=3000 ms liên tục 10 phút với ít nhất 10 request.

## DailyAICostBudgetRisk

- Severity: `warning`; guardrail: `daily cost <= 2.5 USD`; cảnh báo sớm ở 2.0 USD (80%) trong 15 phút.
- Ảnh hưởng: có nguy cơ vượt ngân sách ngày; chưa mặc định là outage người dùng.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Cost over time**, xác nhận tổng ngày và tốc độ tăng chi phí theo phút.
  2. Lọc trace theo model/feature, tìm generation có token output hoặc cost cao bất thường và ghi trace ID.
  3. Tìm log cùng correlation ID, đối chiếu `tokens_in`, `tokens_out`, `cost_usd`; kiểm tra tăng trưởng do traffic hay cost/request.
- Mitigation tạm thời: áp dụng rate limit hoặc quota đã phê duyệt; chuyển model rẻ hơn/giới hạn output token cho feature gây tăng chi phí nếu không làm hỏng chức năng thiết yếu.
- Escalation: báo product owner khi đạt 2.25 USD (90%); báo primary on-call khi vượt 2.5 USD.
- Điều kiện đóng: xác nhận burn rate đã ổn định và dự báo cuối ngày không vượt 2.5 USD; ghi rõ mitigation trong ticket.

## ChatQualityDegraded

- Severity: `warning`; SLO: `quality average >= 0.75`; duy trì: 30 phút, tối thiểu 10 response.
- Ảnh hưởng: câu trả lời vẫn trả về nhưng có khả năng kém hữu ích hoặc sai ngữ cảnh.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Quality proxy**, xác nhận mean <0.75 và phân đoạn theo feature/model nếu dashboard hỗ trợ.
  2. Mở một nhóm trace điểm thấp, kiểm tra retrieval context, prompt version và generation output; ghi trace ID đại diện.
  3. Đối chiếu correlation ID trong log và kiểm tra thay đổi prompt/model gần nhất; xác nhận đây không chỉ là lỗi của quality heuristic.
- Mitigation tạm thời: rollback prompt label/model khi trace chứng minh regression; chuyển sang prompt baseline hoặc fallback đã kiểm thử.
- Escalation: phối hợp `ai-quality-and-sre`; nâng critical nếu có bằng chứng câu trả lời gây tác động nghiêm trọng tới người dùng.
- Điều kiện đóng: quality average >=0.75 liên tục 30 phút với ít nhất 10 response và mẫu trace đã được review.

## Sau sự cố

- Gắn evidence Metrics → Trace → Log vào incident record.
- Ghi root cause, mitigation, fix lâu dài, owner và deadline.
- Review false positive/false negative hàng tuần; điều chỉnh threshold chỉ dựa trên dữ liệu, không thay đổi để che sự cố.
