# 🛠️ TROUBLESHOOTING GUIDE — LEADHUNTER MAINTENANCE

**Dự án:** LeadHunter  
**Mục đích:** Hướng dẫn chẩn đoán và khắc phục sự cố vận hành thường gặp

---

## ❓ 1. CÁC SỰ CỐ THƯỜNG GẶP VÀ CÁCH XỬ LÝ (FAQ & RESOLUTIONS)

### 1. Cảnh báo "Phát hiện nghẽn mạng/Google lag! Đang tạm dừng 3s..."
- **Nguyên nhân:** Google Maps phản hồi chậm hoặc 3 truy vấn liên tiếp không tìm thấy lead thô mới.
- **Xử lý:** Đây là tính năng bảo vệ tự động của bot nhằm tránh bị Google chặn IP. Bot sẽ tự động chạy tiếp sau 3s nghỉ mà không cần can thiệp.

### 2. Giao diện GUI báo "Không thể kết nối CSDL"
- **Nguyên nhân:** File `data/leadhunter.db` bị khóa bởi một ứng dụng khác hoặc đường dẫn không khả dụng.
- **Xử lý:** Kiểm tra quyền ghi thư mục `data/`. Chạy lệnh CLI migration `python3 -m leadhunter.presentation.cli.main` để làm mới CSDL.

### 3. SĐT trùng lặp không được thêm vào CSDL
- **Nguyên nhân:** CSDL SQLite áp dụng `UNIQUE INDEX` trên cột `phone` (Migration 002).
- **Xử lý:** Đây là hành vi chính xác của hệ thống nhằm bảo đảm không xuất hiện SĐT trùng lặp trong danh sách Telemarketing.

---

## 📞 2. BẢO TRÌ BỘ BỘ LỌC TỈNH THÀNH TAM GIÁC VÀNG
Để thay đổi danh sách tỉnh thành ưu tiên, điều chỉnh hàm `_is_in_hcm()` tại file `leadhunter/application/use_cases/auto_run_use_case.py`.
