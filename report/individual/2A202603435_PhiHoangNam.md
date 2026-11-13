# Báo cáo cá nhân — Day 6

Học viên: Phí Hoàng Nam · MSSV 2A202603435 · L3A

## Dữ liệu và pipeline

- **Chủ đề, nguồn/quyền, số trang và quy tắc tính trang:**
  - Chủ đề là tư duy phản biện và logic.
  - Nguồn là giáo trình OpenStax *Introduction to Philosophy* (Rice University), bản PDF 421 trang. Giấy phép CC BY-NC-SA 4.0, được ghi ở trang PDF 4 và cho phép chia sẻ phi thương mại kèm ghi công.
  - Corpus gồm **56 trang nội dung**: chương 2 "Critical Thinking, Research, Reading, and Writing" (trang PDF 51–79, 29 trang) và chương 5 "Logic and Reasoning" (trang PDF 149–175, 27 trang), tổng cộng 184.081 ký tự sau chuẩn hóa.
  - Đã loại bìa, mục lục, phần tóm tắt cuối chương, thuật ngữ, tài liệu tham khảo và câu hỏi ôn tập. Trang được đánh số theo trang vật lý của PDF, bắt đầu từ 1.
  - [data/manifest.json](../../data/manifest.json) ghi số ký tự từng trang, SHA-256 của file và cách tải. File PDF (48 MB) không commit vào repo.
- **Chuẩn hóa, lỗi và giới hạn:**
  - Trích văn bản bằng pypdf 6.21.4, chuẩn hóa Unicode NFC, gộp khoảng trắng trên từng dòng.
  - `load_corpus` báo lỗi khi thiếu file, khi SHA-256 không khớp (bản PDF khác sẽ làm lệch trang gold), khi số trang trích được khác `included_page_count`, và khi gặp trang rỗng.
  - Lần chạy cuối không có trang lỗi hoặc rỗng ([run_log_dev.txt](../../starter/results/run_log_dev.txt) không có dòng WARNING hay ERROR).
  - Giới hạn: header/footer của trang in (ví dụ "148 5 • Logic and Reasoning Access for free at openstax.org") và chú thích hình vẫn còn trong text. Một đoạn văn bị ngắt qua hai trang PDF sẽ thành hai mảnh ở hai trang khác nhau.
- **Embedding, vector store, metric, lệnh chạy và chi phí:**
  - Embedding: `bge-m3:latest` chạy local qua Ollama 0.40.16, digest `7907646426…146bab`, F16, 566,7 triệu tham số, **1024 chiều**. Query và document dùng cùng một model, không thêm prefix, `truncate=false`, batch 16.
  - Vector store: PostgreSQL 16.16 + pgvector 0.8.7 (Docker image `pgvector/pgvector:0.8.7-pg16`), bảng `day6_chunks`. Tìm kiếm **cosine chính xác** (`<=>`, quét tuần tự, không dùng chỉ mục ANN).
  - Lệnh chạy: `python -m src.run --split dev|test` trong thư mục `starter/`. Toàn bộ lệnh setup có trong [README.md](../../README.md).
  - Chi phí **0 USD**, vì không gọi API trả phí.
- **Metadata:**
  - Trường bắt buộc: `document_id` (`source_id` trong manifest), `source` (URL OpenStax), `page` (trang PDF) và `chunk_id` dạng `document:page:strategy:index`.
  - Trường lọc bổ sung: `chapter` (`critical_thinking` hoặc `logic_and_reasoning`), lấy từ khoảng trang của chương trong manifest, không đoán. Thêm `language` = `en`.
  - Lý do chọn `chapter`: corpus có hai phạm vi tách biệt rõ, và người học thường biết mình đang đọc chương nào. Một số khái niệm xuất hiện ở cả hai chương (ví dụ strawman được nhắc ở chương 2 trang 64 và định nghĩa ở chương 5 trang 174).

## Cấu hình và benchmark

Tôi chọn cấu hình A dựa trên kết quả dev, ưu tiên Evidence Hit@3 và dùng Hit@1 khi hòa. A đạt Evidence Hit@3 là 11/15, còn B và C đều đạt 10/15. Cả ba đều đạt Hit@1 là 6/15. Cấu hình A được chốt ở 500 ký tự mỗi chunk và overlap 50 ký tự trước khi chạy tập test.

- **A / B / C:**
  - **A:** `fixed_size`, cửa sổ 500 ký tự, overlap 50, trên text đã gộp khoảng trắng của từng trang (không vượt ranh giới trang). Không filter. Kết quả: 432 chunk.
  - **B:** `by_paragraph`, tách theo dòng trống thành đoạn; đoạn dài hơn 500 ký tự được gom theo câu sao cho không quá 500; câu dài hơn 500 ký tự được cắt bằng `textwrap`. Không filter. Kết quả: 454 chunk.
  - **C:** dùng lại chunk và vector của B, chỉ thêm `WHERE metadata @> {"chapter": ...}` khi câu hỏi có filter. **B–C chỉ khác nhau đúng một yếu tố là metadata filter.** A–B chỉ khác cách chunk; model, store, metric và top-k giữ nguyên.
- **Benchmark:**
  - 20 câu trong [benchmark/questions.json](../../benchmark/questions.json): câu hỏi viết bằng tiếng Việt, evidence trích nguyên văn tiếng Anh. Split 15 dev / 5 test được chốt trước khi chạy.
  - Gold trải trên cả hai chương: 9 câu thuộc critical_thinking, 11 câu thuộc logic_and_reasoning. Có câu hỏi trực tiếp (q03, q19), câu diễn đạt lại hoặc tình huống (q16, q18) và câu có điều kiện (q01, q12).
  - **3 câu có filter**: q01 và q06 (dev), q18 (test). Giá trị filter được cung cấp trong ngữ cảnh câu hỏi, ví dụ q18 "Tôi đang đọc chương Logic and Reasoning".
  - Evidence được kiểm chứng bằng `python -m scripts.verify_benchmark`: 20/20 đoạn evidence nằm trên đúng trang gold sau chuẩn hóa, và filter khớp chương của trang gold ([benchmark_verification.json](../../starter/results/benchmark_verification.json)).
- **Tiêu chí chọn chiến lược (chốt trước khi xem test):** ưu tiên Evidence Hit@3 trên dev, rồi đến Hit@1. Theo tiêu chí này A được chọn. Test chỉ chạy sau khi đã chốt. Không có tham số nào được chỉnh sau khi xem test.

## Kết quả

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian ingest | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 6/15 | 11/15 | 432 | 9,1 giây | 0 USD |
| B | dev | 6/15 | 10/15 | 454 | 9,4 giây | 0 USD |
| C | dev | 6/15 | 10/15 | 454 (dùng chung B) | 0 (dùng lại B) | 0 USD |
| A | test | 3/5 | 4/5 | 432 | 9,2 giây | 0 USD |
| B | test | 3/5 | 3/5 | 454 | 9,4 giây | 0 USD |
| C | test | 3/5 | 3/5 | 454 (dùng chung B) | 0 (dùng lại B) | 0 USD |

Ghi chú về bảng trên:

- Chỉ số phụ Page Hit@3 (top-3 có ít nhất một chunk thuộc trang gold, không yêu cầu đủ evidence): A 13/15 dev, 5/5 test; B và C 12/15 dev, 4/5 test.
- Độ dài chunk: A có trung vị 500 ký tự, trung bình 470, nhỏ nhất 54. B có trung vị 432, trung bình 405, nhỏ nhất 29, và 7 chunk dưới 100 ký tự.
- Tổng thời gian truy vấn qua ba cấu hình là 2,012 giây cho 20 câu, gồm 1,489 giây cho dev và 0,523 giây cho test.
- Nạp lại không bị nhân đôi: số dòng trước và sau mỗi lần upsert đều bằng 432 (A) và 454 (B), số `chunk_id` khác nhau cũng bằng số dòng (`reload_check` trong `summary_*.json`).

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 1,0 (n=10) | 15/15 | test 0/1; dev 2/2 | 0 / 1 / 4 → 1,8 |
| B | 1,7 (n=10) | 15/15 | test 1/1; dev 2/2 | 1 / 0 / 4 → 1,6 |
| C | 1,7 (n=10, dùng chung chunk với B) | 15/15 | test 1/1; dev 2/2 | 1 / 0 / 4 → 1,6 |

**Đường dẫn trace, nhãn thủ công và cách chọn mẫu:**

- Trace top-3 đầy đủ (text, score, metadata, trạng thái khớp evidence): [traces_dev.json](../../starter/results/traces_dev.json), [traces_test.json](../../starter/results/traces_test.json).
- Nhãn và lý do: [starter/results/manual_labels/](../../starter/results/manual_labels/).
- Mẫu coherence là 10 trang có ID nhỏ nhất (trang 51–60). Trên mỗi trang, vị trí được chấm là câu chứa điểm giữa trang. Quy tắc này được chốt trước khi chấm.
- Metadata và grounding được chấm trên toàn bộ 5 câu test × top-3. Mẫu được xuất bằng `python -m scripts.export_audit`.

## Phân tích và kết luận

- **So sánh A–B (chỉ đổi cách chunk):**
  - A hơn B một câu Evidence Hit@3 ở cả dev (11 so với 10) và test (4 so với 3). Hit@1 bằng nhau.
  - Trên 10 vị trí được audit, B đạt coherence trung bình 1,7/2 và A đạt 1,0/2. Cả 10 mẫu A được chấm 1/2 vì có chỗ cắt giữa từ hoặc giữa ý.
  - Lợi thế của A đến từ overlap và kích thước đều: một câu evidence dài có thể nằm trọn trong cửa sổ 500 ký tự. B lại sinh ra những mảnh rất ngắn ở chỗ đoạn văn bị ngắt trang, và các mảnh này vẫn có điểm cosine cao.
  - Chênh lệch chỉ là 1 câu trên 15 và 1 câu trên 5, nên **không đủ để khẳng định A tốt hơn B một cách tổng quát**.
- **So sánh B–C (chỉ thêm filter):**
  - C cho top-3 giống hệt B ở cả 3 câu có filter. Lý do là bge-m3 vốn đã trả về chunk đúng chương: B tuân thủ filter 3/3 ngay cả khi không lọc.
  - Ở q18, A truy vấn không lọc và trả một chunk ngoài phạm vi ở hạng 2 (trang 64, chương `critical_thinking`). C áp dụng filter `logic_and_reasoning` và giữ nguyên top 3 của B vì cả ba chunk của B đã thuộc chương yêu cầu.
- **Ví dụ sai 1, q17 (test), lỗi do mảnh chunk của B:**
  - Rank 1–2 của B là `…:175:B:4` ("assumption—rely on information or beliefs that require further justification") và `…:159:B:5` ("the premises being advanced for a conclusion.", 45 ký tự).
  - Mảnh thứ hai là phần đuôi của một câu bị ngắt sang trang PDF 159. Nó không mang nội dung nhưng lại khớp chung chung với nhiều câu hỏi về "tiền đề": cũng chính mảnh này đứng hạng 1 ở q13 (dev).
  - A đạt grounding 1 ở câu này nhờ phần giải thích chung trên trang 173. Top 3 của A thiếu câu "premise 1… A and B are the only options".
- **Ví dụ sai 2, q12 (dev), evidence bị cắt qua ranh giới chunk:**
  - A lấy được `…:162:A:8` nhưng chunk này kết thúc ở "An instance of a deductive argument where the premises are all true 152 5 • Logic and Reasoning Access for free at openstax.org", tức là lẫn footer trang in và không chứa trọn câu evidence.
  - B lấy được trang 162 hai lần (`…:162:B:8`, `…:162:B:5`) nhưng đều là câu lân cận chứ không phải câu evidence.
  - Theo định nghĩa Hit chặt (phải chứa **đủ** evidence), cả ba cấu hình đều trượt.
- **Ví dụ về độ chặt của metric, q18 (test) và q08 (dev):**
  - Ở q18, B và C không có câu evidence gold, nhưng bảng 5.3 ở trang 175 ("Strawman — utilizes a weaker version of the position… easier to defeat") đủ để trả lời. Vì vậy grounding thủ công cho 2, trong khi Evidence Hit@3 tính là 0.
  - Ở q08, B lấy được đoạn "Close Read" ở trang 74, đúng ý câu hỏi, nhưng gold lại đặt ở danh sách tóm tắt trang 75.
  - Đây là giới hạn khi chỉ ghi một trang gold cho mỗi câu.
- **Chiến lược chọn, đánh đổi và điều kiện áp dụng:**
  - Theo tiêu chí đã chốt, chọn **A** (500/50).
  - Đánh đổi: A có recall bằng chứng tốt hơn một chút và grounding test 1,8 so với 1,6. B có chunk dễ đọc và tự đứng được hơn, phù hợp khi chunk được đưa nguyên cho LLM hoặc hiển thị cho người dùng.
  - Nếu ưu tiên coherence, nên dùng B và đặt độ dài tối thiểu cho chunk.
  - Filter theo `chapter` (C) nên giữ cho các corpus có nhiều chương chồng chủ đề, hoặc khi người dùng chỉ định phạm vi. Trên corpus này nó chỉ là cơ chế an toàn: không làm hại, cũng không làm lợi.
- **Hạn chế:**
  - Test chỉ có 5 câu, nên một câu tương ứng 20 điểm phần trăm; dev 15 câu. Chênh lệch một câu trên mỗi tập chỉ mô tả kết quả trên benchmark này.
  - Mỗi câu chỉ có một trang gold. Chỉ có 3 câu filter, và đều không phân biệt được B với C.
  - Nhãn coherence và grounding được chấm với sự hỗ trợ của trợ lý AI (Claude): AI đọc toàn văn từng chunk theo đúng thang điểm trong GUIDE và ghi lý do cho từng nhãn. Sau đó học viên (tác giả) đã rà soát toàn bộ nhãn so với chunk gốc và đồng ý, không sửa nhãn nào. Người chấm biết trước điểm Hit@k nên có nguy cơ thiên lệch, và không có người chấm thứ hai. Mọi nhãn đều kèm lý do và chunk gốc trong `starter/results/audit/` để người chấm có thể đối chiếu lại.
  - Thời gian đo trên một máy, chạy một lần, đã gồm cả gọi Ollama và ghi DB. Ollama đã nạp sẵn model nên chưa tính thời gian khởi động lần đầu.
  - Metadata `page` là trang PDF, không phải số trang in trong sách (lệch khoảng 10 trang ở chương 5). Người dùng trích theo sách in có thể bị nhầm.
- **Nếu làm lại hoặc mở rộng:**
  - Ghép text liền mạch qua ranh giới trang trước khi chunk, nhưng vẫn giữ `page_start` và `page_end`.
  - Bỏ header/footer trang in. Gộp các mảnh ngắn dưới khoảng 150 ký tự vào chunk liền kề.
  - Cho phép nhiều trang gold hoặc bằng chứng tương đương cho mỗi câu.
  - Thêm câu hỏi có khái niệm xuất hiện ở cả hai chương để thực sự kiểm tra filter, viết từ đầu trên một tập test mới, vì không được sửa tập test hiện tại.
  - Thử thêm hybrid BM25 + dense.

## Công cụ AI đã dùng

Tôi dùng ChatGPT để hỗ trợ viết mã pipeline, soạn câu hỏi benchmark và đối chiếu trace. Tôi dùng Claude Code (Anthropic) để hỗ trợ viết code bổ sung (log và kiểm tra version, kiểm tra nạp lại, `verify_benchmark.py`, `export_audit.py`), đề xuất nhãn audit và soạn báo cáo. Mọi số liệu đều lấy từ các file kết quả do pipeline tự sinh ra. Pipeline đã được chạy lại 3 lần và cho cùng kết quả. Nhãn coherence và grounding do AI đề xuất, sau đó tôi đã rà soát và xác nhận, như đã nêu ở phần Hạn chế. Metadata được kiểm tra tự động so với PDF và manifest (45/45 bản ghi đạt).
