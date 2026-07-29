# 🚀 LeadHunter Bot - Thợ Săn Số Điện Thoại Tốc Độ Cao

Bot tự động cào số điện thoại khách hàng tiềm năng từ Google Maps. Được thiết kế đặc biệt cho dân Sales với tiêu chí: **Nhanh - Gọn - Sạch**.

---

## 🌟 Các Tính Năng Nổi Bật
- **Cơ chế 3 Nhân Đa Luồng:** Bot giả lập cùng lúc 3 thiết bị (Windows, Mac, Linux) để tăng tốc độ cào mà không bị Google chặn. 
- **Chế Độ Chạy Ngầm (Silent Mode):** Màn hình gọn gàng sạch sẽ, chỉ hiện một thanh tiến trình duy nhất (🏍︎) đang chạy đua đến 100%.
- **Sàng Lọc Kim Cương:** 
  - ❌ Tự động vứt bỏ các công ty đã có Website (chỉ lấy khách chưa có web để dễ chốt sale).
  - ❌ Tự động lọc bỏ các số rác, số bàn, số tổng đài (chỉ lấy số di động).
  - ❌ Chống trùng lặp tuyệt đối (không bao giờ cào lại số đã có trong Database).
- **Chia Bài Toán Học:** Nếu nhập nhiều từ khóa, bot sẽ tự động chia đều KPI (VD: Cào 80 số cho 3 từ khóa thì nó sẽ tự chia 27-27-26).
- **Xuất Excel Chuẩn Form:** File xuất ra luôn có cột "Tình Trạng" được kéo giãn rộng rãi bạt ngàn để sếp dễ dàng nhập chú thích ("gọi không nghe", "chốt đơn", v.v...).

---

## 🛠 HƯỚNG DẪN CÀI ĐẶT TRÊN MÁY MỚI (CHỈ MẤT 3 PHÚT)

### 📌 BƯỚC 1: Cài đặt Python 3.12 (Bắt buộc dùng bản 3.12)
1. Tải bản Python 3.12 chuẩn từ link: 👉 **[Download Python 3.12](https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe)**
2. Mở file cài đặt lên, **NHÌN XUỐNG GÓC DƯỚI CÙNG VÀ TÍCH VÀO Ô:**
   ☑️ **`Add python.exe to PATH`** *(Rất quan trọng! Quên tích ô này sẽ bị lỗi lệnh)*
3. Bấm **Install Now** cho nó cài xong.

### 📌 BƯỚC 2: Kích hoạt Bot (Chỉ làm 1 lần duy nhất)
Mở **CMD** hoặc **PowerShell** trên máy đó lên, trỏ vào thư mục `bot` và dán 4 dòng lệnh này:

```cmd
cd /d D:\bot
pip install -e .
playwright install chromium
reset
```
*(Thay `D:\bot` bằng đúng đường dẫn thư mục chứa bot trên máy đó).*

---

## 📜 BẢNG CỬU CHƯƠNG LỆNH (CHEAT SHEET)

Hệ thống đã được thiết kế tối giản nhất với 4 lệnh siêu ngắn gọn: **`cao`**, **`xuat`**, **`huy`**, và **`reset`**. Bạn cứ gõ trực tiếp lệnh vào Terminal/CMD là nó chạy!

### 1. ⚔️ Nhóm Lệnh Đi Săn (Cào Dữ Liệu)
Mặc định mỗi lần chạy, bot sẽ tự động cào **vừa đủ 80 số** rồi tự xuất ra file Excel. 
- `cao "Cửa cuốn"` : Lấy 80 số cho 1 ngành duy nhất.
- `cao "giáo dục, cân điện tử, xây dựng"` : Cào 80 số, chia đều tăm tắp cho cả 3 ngành.
- `cao "Nội thất" -t 50` : Cào số lượng tùy chọn (thay đổi mục tiêu bằng `-t 50`, `-t 100`...).

### 2. 📦 Nhóm Lệnh Xử Lý Nhanh
- `xuat` : Lập tức trích xuất 80 số mới nhất ra 1 file Excel mới (Dùng khi lỡ tay xóa mất file Excel cũ, muốn xuất lại mà không cần cào thêm).
- `huy` : Lệnh "Uống thuốc hối hận"! Lỡ cào nhầm từ khóa rác? Gõ lệnh này để **xóa sạch** toàn bộ tàn dư của đợt cào vừa rồi ra khỏi Database, trả lại sự trong sạch cho dữ liệu.
- `reset` : Nút bấm hạt nhân! ☢️ Xóa sạch trắng toàn bộ Database và file Excel cũ để bắt đầu một chiến dịch hoàn toàn mới từ con số 0.

---

💡 **MẸO XỬ LÝ NẾU MÁY BỊ LỖI LẠ (BỊ NHẦM PHIÊN BẢN PYTHON):**
Nếu mở CMD gõ `cao` hay `pip` không nhận diện, bạn mở PowerShell/CMD dán dòng này để khóa cứng bản Python 3.12 làm mặc định:
`setx PY_PYTHON 3.12`
Sau đó tắt CMD đi mở lại là chạy mượt mà ngay!


