# 🎯 LeadHunter — Automated Sales Lead Extraction Engine

**LeadHunter** là hệ thống tự động cào, lọc và chuẩn hóa dữ liệu khách hàng tiềm năng (Leads) từ Google Maps dành cho khối doanh nghiệp kinh doanh tại Việt Nam, đặc biệt tối ưu cho khu vực **Tam Giác Vàng (TP.HCM, Bình Dương, Đồng Nai)**.

---

## 🚀 Tính năng nổi bật (Features)

- **Cào dữ liệu đa luồng tốc độ cao:** Sử dụng Playwright Chromium với công nghệ giải mã RPC JSON ngầm kết hợp cào DOM fallback (~52 leads/giây).
- **Bộ lọc thông minh 4 tầng (4-Stage Smart Filters):**
  1. **Lọc nhà mạng viễn thông (Telecom Filter):** Nhận diện chính xác Viettel, Vina, Mobi; loại bỏ số máy bàn (`024`, `028`) và tổng đài (`1900`, `1800`).
  2. **Lọc địa lý (Geographic Scope Filter):** Tự động nhận diện các biến thể địa danh `HCM`, `TP.HCM`, `Hồ Chí Minh`, `Sài Gòn`, `Dĩ An`, `Biên Hòa` và lọc bỏ các địa chỉ ngoài phạm vi (Hà Nội, Cần Thơ, Long An...).
  3. **Lọc chính sách Website (Website Policy Filter):** Phân biệt website tên miền riêng và đường dẫn mạng xã hội (Facebook, Zalo, Shopee).
  4. **Lọc trùng lặp 2 tầng (Deduplication Engine):** Tra cứu RAM `O(1)` tốc độ $0.068\mu s$/phép toán kết hợp chỉ mục `UNIQUE INDEX` trên CSDL SQLite.
- **Dynamic Target Overflow Compensation:** Tự động điều phối cào bù giữa các từ khóa khi có một từ khóa bị thiếu hụt dữ liệu để luôn đạt đủ tổng chỉ tiêu chiến dịch (`TARGET`).
- **Giao diện đa nền tảng:** Hỗ trợ cả giao diện đồ họa **Desktop App GUI** (PyWebView) và giao diện dòng lệnh **CLI** (Click).

---

## 🏛️ Kiến trúc phần mềm (Architecture)

Hệ thống được thiết kế theo chuẩn **Clean Architecture & Domain-Driven Design (DDD)**:

```text
Presentation Layer (PyWebView GUI / Click CLI)
          │
          ▼
Application Layer (Use Cases & Ports)
          │
          ▼
Domain Layer (Entities, Value Objects, Domain Services)
          ▲
          │ (Dependency Inversion)
Infrastructure Layer (SQLite Persistence, Playwright Scraper, Excel Writer)
```

---

## 🛠️ Hướng dẫn cài đặt & Vận hành (Quick Start)

### 1. Yêu cầu hệ thống
- Python 3.10+ (Khuyên dùng Python 3.12)
- Operating System: Linux / macOS / Windows

### 2. Cài đặt môi trường (Setup)

#### 💻 Cho máy Windows:
- **Tải nhanh 1-Click**: Nhấp đúp chuột vào file `setup.bat`.
- **Hoặc gõ lệnh**:
  ```cmd
  git clone -b master https://github.com/hanh2k5/bot.git
  cd bot
  setup.bat
  ```

#### 🍎 Cho máy macOS / Linux:
- **Tải & cài đặt 1-Click**:
  ```bash
  git clone -b master https://github.com/hanh2k5/bot.git
  cd bot
  python3 -m pip install -e . && python3 -m playwright install chromium
  ```
- **Tạo phím tắt `run` khởi chạy nhanh trên Mac (Chỉ làm 1 lần)**:
  ```bash
  echo 'alias run="python3 "\$PWD/gui_app.py""' > ~/.zshrc && source ~/.zshrc
  ```

### 3. Chạy giao diện Desktop GUI
```bash
run
# Hoặc:
python3 gui_app.py
```

### 4. Chạy chiến dịch từ dòng lệnh CLI
```bash
python3 auto_run.py
# Hoặc chạy lệnh CLI đầy đủ:
python3 -m leadhunter.presentation.cli.main run --keywords "xây dựng,nha khoa,pccc" --target 80
```

### 5. Chạy toàn bộ Test Suite
```bash
/home/acer/.local/bin/pytest tests/ -v
```

---

## 📊 Benchmark Hiệu năng (Performance Benchmark)

- **Tra cứu 100k SĐT trong bộ 1M RAM:** $0.068\mu s$/SĐT ($\approx 14.6$ triệu phép tra cứu/giây).
- **Peak RAM Footprint:** 44.12 MB
- **Thời gian chạy E2E Campaign 80 leads:** 1.512 giây (~52 leads/giây).
- **Test Suite Status:** **180 Passed / 0 Failed (100% Pass)**.

---

## 📚 Tài liệu chi tiết (Documentation)

Chi tiết thiết kế và tài liệu kỹ thuật được lưu tại thư mục `docs/`:
- [Architecture Documentation](docs/architecture.md)
- [Data Flow Pipeline](docs/data-flow.md)
- [Database Schema & Migrations](docs/database.md)
- [Scraper Adapter Specification](docs/scraping.md)
- [Testing Strategy & Regression Proof](docs/testing.md)
- [Performance Benchmark](docs/benchmark.md)
- [Troubleshooting Guide](docs/troubleshooting.md)
- [Codebase Inventory](docs/codebase_inventory.md)
