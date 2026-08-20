# 🗄️ DATABASE DOCUMENTATION — LEADHUNTER PERSISTENCE

**Dự án:** LeadHunter  
**Hệ quản trị CSDL:** SQLite 3  
**Vị trí file:** `data/leadhunter.db`  

---

## 📋 1. SƠ ĐỒ BẢNG DỮ LIỆU (`leads`)

Bảng `leads` lưu trữ toàn bộ thông tin khách hàng tiềm năng thu thập được:

| Tên Cột | Kiểu Dữ Liệu | Constraints | Mô Tả |
|---|---|---|---|
| `id` | `TEXT` | `PRIMARY KEY` | UUIDv4 định danh duy nhất bản ghi |
| `company_name` | `TEXT` | `NOT NULL` | Tên công ty / địa điểm kinh doanh |
| `contact_name` | `TEXT` | Default `''` | Tên người liên hệ (nếu có) |
| `email` | `TEXT` | Default `''` | Địa chỉ email |
| `phone` | `TEXT` | Default `''` | Số điện thoại di động chuẩn hóa 10 chữ số |
| `website` | `TEXT` | Default `''` | Địa chỉ trang web hoặc trang cá nhân |
| `address` | `TEXT` | Default `''` | Địa chỉ hoạt động |
| `source` | `TEXT` | Default `'google_maps'` | Nguồn dữ liệu (`google_maps` / `excel`) |
| `source_reference` | `TEXT` | Default `''` | Tham chiếu nguồn gốc (URL / tên file) |
| `status` | `TEXT` | Default `'NEW'` | Trạng thái (`NEW`, `VALIDATED`, `EXPORTED`...) |
| `score` | `INTEGER` | Default `0` | Điểm đánh giá tiềm năng |
| `notes` | `TEXT` | Default `''` | Ghi chú bổ sung |
| `created_at` | `TEXT` | `NOT NULL` | Thời gian tạo (ISO-8601 UTC) |
| `updated_at` | `TEXT` | `NOT NULL` | Thời gian cập nhật gần nhất (ISO-8601 UTC) |
| `import_batch_id` | `TEXT` | `NULL` | ID đợt cào dữ liệu (dùng để rollback) |
| `phone_normalized` | `INTEGER` | Default `0` | Cờ đánh dấu SĐT đã được chuẩn hóa |

---

## ⚡ 2. CHỈ MỤC & RÀNG BUỘC CHỐNG TRÙNG (INDEXES & CONSTRAINTS)

### 2.1. Migration 001 (`001_initial_schema.sql`)
- Khởi tạo bảng `leads`, `lead_status_history`.
- Tạo các chỉ mục tra cứu thông thường:
  - `idx_leads_phone` trên `leads(phone)`
  - `idx_leads_email` trên `leads(email)`
  - `idx_leads_status` trên `leads(status)`
  - `idx_leads_import_batch_id` trên `leads(import_batch_id)`

### 2.2. Migration 002 (`002_add_unique_phone_index.sql`)
- Xóa sạch dữ liệu trùng cũ bằng câu lệnh lọc giữ lại `MIN(ROWID)`.
- Tạo chỉ mục độc nhất Partial Unique Index:
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_phone_unique 
ON leads(phone) 
WHERE phone != '' AND phone IS NOT NULL;
```
- **Ý nghĩa:** Bảo đảm không thể xuất hiện 2 bản ghi có cùng SĐT trong CSDL tại tầng Engine CSDL.

---

## 🔒 3. QUẢN LÝ GIAO DỊCH & AN TOÀN ĐA LUỒNG (TRANSACTION & CONCURRENCY)

- **ConnectionManager:** Quản lý kết nối an toàn đa luồng (`thread-safe`). Context manager `cm.transaction()` tự động thực hiện `COMMIT` khi thành công và `ROLLBACK` khi phát sinh ngoại lệ `sqlite3.Error`.
- **Integrity Error Recovery:** Trong `SqliteLeadRepository.add()`, khi phát sinh `sqlite3.IntegrityError` do trùng SĐT, repository tự động bắt ngoại lệ, truy vấn lại bản ghi hiện có và trả về mà không làm sập ứng dụng.
