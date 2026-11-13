# Pipeline PostgreSQL + pgvector

Xem mục **Tái lập** trong [README gốc](../README.md) để cài môi trường, tải corpus và khởi động PostgreSQL cùng Ollama. Bản PDF và các trang dùng trong lab được mô tả trong [manifest](../data/manifest.json).

## Cấu trúc

```text
starter/
├── docker-compose.yml     # PostgreSQL 16 + pgvector, chỉ mở cổng local
├── init.sql               # bật extension khi tạo database mới
├── requirements.txt       # psycopg, pypdf và python-dotenv
├── .env.example           # cấu hình mẫu; copy thành .env
├── scripts/check_setup.py # kiểm tra kết nối và extension (đã chạy được)
├── src/
│   ├── models.py          # cấu trúc dữ liệu trang và chunk
│   ├── ingestion.py       # đọc / chuẩn hóa tài liệu
│   ├── chunking.py        # chia chunk
│   ├── embeddings.py      # embedding BGE-M3 qua Ollama
│   ├── store.py           # lưu vector, metadata và filter
│   ├── evaluation.py      # chấm truy xuất, lưu trace
│   └── run.py             # kết nối các bước thành pipeline
├── data/                  # bạn tự chuẩn bị corpus được phép sử dụng
└── results/               # lưu kết quả của bạn
```

## Chạy benchmark

Từ thư mục `starter/` sau khi thiết lập môi trường:

```powershell
python scripts/check_setup.py
python -m scripts.verify_benchmark
python -m src.run --split dev
# Chốt cấu hình dựa trên dev trước khi chạy test.
python -m src.run --split test
python -m scripts.export_audit
```

Kết quả nằm trong [results/](results/). Xem [báo cáo cá nhân](../report/individual/2A202603435_PhiHoangNam.md) để biết cấu hình, chỉ số và nhãn audit.
