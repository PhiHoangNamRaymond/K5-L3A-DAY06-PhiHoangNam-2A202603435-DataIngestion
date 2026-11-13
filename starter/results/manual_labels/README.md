# Nhãn đánh giá thủ công

| File | Nội dung | Mẫu |
|---|---|---|
| `coherence_labels.csv` | Chunk coherence 0/1/2 | 10 vị trí × A, B (C dùng chung chunk với B) |
| `metadata_labels.csv` | `source`, `page`, `chapter`, `language` đủ và đúng; tuân thủ filter | 5 câu test × top-3 × A/B/C = 45 bản ghi |
| `grounding_labels.csv` | Grounding 0/1/2 của top-3 | 5 câu test × A/B/C |

## Cách chọn mẫu (chốt trước khi xem điểm)

- **Coherence:** 10 trang có ID nhỏ nhất trong corpus (trang PDF 51–60). Trên mỗi trang, vị trí được chấm là câu chứa ký tự ở giữa trang sau chuẩn hóa. Với mỗi chiến lược, lấy chunk chứa phần đầu câu đó. Sinh lại mẫu bằng `python -m scripts.export_audit`, kết quả ở `../audit/coherence_samples.json`.
- **Metadata và grounding:** toàn bộ 5 câu test, top-3 của mỗi chiến lược, lấy từ `../traces_test.json`. Văn bản đầy đủ của từng hit có trong `../audit/test_top3_samples.json`.

## Thang điểm (theo GUIDE.md)

- **Coherence:** 0 = bị cắt giữa ý hoặc thiếu chủ thể nên không hiểu được; 1 = hiểu một phần, thiếu ngữ cảnh; 2 = tự hiểu được và giữ trọn ý.
- **Grounding:** chỉ đánh giá bằng chứng truy xuất được, không đánh giá câu trả lời của LLM. 0 = không có bằng chứng; 1 = có nhưng thiếu điều kiện hoặc ngữ cảnh; 2 = đủ để trả lời và truy nguồn. Bằng chứng tương đương ngoài trang gold được chấp nhận nếu người chấm xác nhận, và lý do được ghi trong cột `reason`.
- **Metadata:** một bản ghi được tính là đủ và đúng khi `source` khớp manifest, `page` khớp trang PDF chứa đoạn text đó, `chapter` khớp khoảng trang của chương trong manifest, và `language` = `en`. Ba điều kiện đầu được kiểm tra tự động trong `export_audit.py` (cột `auto_check`), sau đó đọc lại từng chunk.

## Người chấm và nguy cơ thiên lệch

Nhãn coherence và grounding được chấm với sự hỗ trợ của trợ lý AI (Claude, Anthropic): AI đọc toàn văn từng chunk theo đúng thang trên và ghi lý do cho từng nhãn. Sau đó học viên (tác giả) đã rà soát toàn bộ nhãn so với chunk gốc và xác nhận, không sửa nhãn nào. Người chấm biết trước điểm Hit@k tự động nên có thể bị thiên lệch. Để giảm thiên lệch, mẫu được chọn theo quy tắc cố định và mỗi nhãn đều kèm lý do có thể kiểm chứng.
