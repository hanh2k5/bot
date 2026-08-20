# 📌 REMAINING TECHNICAL DEBT — LEADHUNTER PROJECT

**Dự án:** LeadHunter  
**Ngày lập:** 2026-08-11  

---

## 📝 DANH SÁCH NỢ KỸ THUẬT CẦN LƯU Ý KHI PHÁT TRIỂN NÂNG CAO

### 1. Phụ thuộc vào giao thức ngầm của Google Maps RPC
- **Mô tả:** Code bóc tách gói tin RPC JSON dựa trên định dạng phản hồi hiện tại của Google Maps.
- **Lý do không refactor:** Hiện tại hệ thống đã có sẵn fallback cào thẻ DOM. Việc rewrite lại toàn bộ parser RPC khi chưa có sự thay đổi từ Google là không cần thiết và có nguy cơ gây lỗi không đáng có.
- **Khuyến nghị tương lai:** Theo dõi định kỳ nếu Google thay đổi cấu trúc gói RPC.

### 2. GUI PyWebView Backend tích hợp HTTP Server đơn giản
- **Mô tả:** `gui_app.py` sử dụng `HTTPServer` tiêu chuẩn của Python để tương tác với frontend `index.html`.
- **Lý do không refactor:** Kiến trúc hiện tại đáp ứng tốt tốc độ phản hồi 50ms, dung lượng nhỏ gọn không cần cài thêm các framework cồng kềnh như FastAPI hay Flask.
- **Khuyến nghị tương lai:** Giữ nguyên thiết kế tối giản này.
