# 🕷️ SCRAPING ENGINE DOCUMENTATION — LEADHUNTER ADAPTER

**Dự án:** LeadHunter  
**Thư viện cốt lõi:** Playwright Chromium (Python)  
**Tốc độ cào trung bình:** ~52 leads/giây (với dữ liệu mạng ổn định)

---

## 🚀 1. KỸ THUẬT BÓC TÁCH KÉP (DUAL-MODE SCRAPING ENGINE)

`GoogleMapsScraper` sử dụng cơ chế bóc tách dữ liệu 2 tầng tiên tiến:

```text
               ┌────────────────────────────────────────┐
               │    Google Maps Query Input Search      │
               └──────────────────┬─────────────────────┘
                                  │
                 ┌────────────────┴────────────────┐
                 ▼                                 ▼
      [ƯU TIÊN 1: Network RPC]           [RESERVE 2: DOM Scraper]
      - Bắt gói tin JSON ngầm           - Cuộn danh sách tự động
      - Trích xuất tốc độ cao           - Cào thẻ HTML .hfday
      - Tránh nghẽn DOM render          - Chờ phần tử xuất hiện
```

1. **Ưu tiên 1 (Network Response Interception):** Bắt và giải mã trực tiếp các gói tin RPC JSON ngầm được Google Maps trả về khi cuộn danh sách. Phương pháp này cho tốc độ cào nhanh gấp 5-10 lần và tiết kiệm tài nguyên CPU/RAM tối đa.
2. **Ưu tiên 2 (DOM Parsing Fallback):** Nếu Google không sử dụng RPC JSON hoặc gói tin bị mã hóa thay đổi cấu trúc, hệ thống tự động chuyển sang cào các phần tử thẻ HTML DOM danh sách địa điểm.

---

## 🛡️ 2. CHỐNG NGHẼN MẠNG & AN TOÀN ĐA LUỒNG (NETWORKING & THROTTLING)

- **Xoay vòng User-Agent:** Mỗi worker thread được cấp phát ngẫu nhiên User-Agent thuộc 3 hệ điều hành phổ biến (Linux, macOS, Windows) nhằm giảm thiểu khả năng bị phát hiện thiết bị tự động.
- **Cơ chế Cooldown Tự Động:** Nếu 3 truy vấn liên tiếp trong chiến dịch trả về 0 kết quả (do Google lag hoặc nghẽn mạng), hệ thống phát cảnh báo và tự động tạm dừng 3 giây (`time.sleep(3)`) trước khi tiếp tục.
- **Bảo đảm Dọn dẹp Tài nguyên (Resource Cleanup):** Toàn bộ Browser Instance, Browser Context và Page được đưa vào khối `try/finally` để bảo đảm đóng sạch sẽ ngay cả khi xảy ra sự cố đột ngột hoặc người dùng ấn Hủy chiến dịch.
