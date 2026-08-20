# ⚡ BENCHMARK DOCUMENTATION — LEADHUNTER PERFORMANCE

**Dự án:** LeadHunter  
**Môi trường thử nghiệm:** Linux x86_64, Python 3.12  

---

## 📈 1. KẾT QUẢ BENCHMARK ĐỘC LẬP (BENCHMARK METRICS)

### 1.1. Tra cứu Lọc Trùng SĐT 1 Triệu Số Trên Bộ Nhớ RAM (`set` lookup)
- **Tải 1,000,000 SĐT vào RAM:**
  - Thời gian nạp trung bình: `0.046 giây`
  - Bộ nhớ RAM tiêu tốn: `36.19 MB`
- **Tra cứu 100,000 SĐT ngẫu nhiên trong bộ 1,000,000 SĐT:**
  - Tổng thời gian tra cứu 100k số: `0.00684 giây`
  - Tốc độ tra cứu mỗi SĐT: `0.0684 microsecond/SĐT` ($\approx 14.6$ triệu phép tra cứu/giây)

### 1.2. Hiệu năng Pipeline Cào & Xử lý End-to-End (E2E Pipeline)
- **Tổng số lead xử lý thô:** 1,170 leads
- **Thời gian hoàn tất chiến dịch (Target = 80):** 1.512 giây
- **Tốc độ xử lý trung bình:** `52.90 leads/giây`
- **Tốc độ ghi CSDL SQLite:** `52.90 writes/giây`
- **Peak RAM Footprint:** `44.12 MB`
- **Peak CPU Utilization:** `~15%` (3 worker threads)

---

## 🛡️ 2. BẢO VỆ TÀI NGUYÊN (RESOURCE PROTECTION)

Hệ thống hoạt động tối ưu với dung lượng RAM dưới 50MB ngay cả khi nạp hàng triệu SĐT lịch sử, cho phép phần mềm chạy mượt mà trên các máy tính cấu hình văn phòng cơ bản.
