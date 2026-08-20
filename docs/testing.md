# 🧪 TESTING DOCUMENTATION — LEADHUNTER VERIFICATION

**Dự án:** LeadHunter  
**Khung kiểm thử:** Pytest 8.3.5  
**Tổng số test cases:** **180 Passed (0 Failed)**  
**Thời gian chạy trung bình:** ~1.13 seconds (Unit/Integration)

---

## 📁 1. CẤU TRÚC TEST SUITE (TEST DISTRIBUTION)

Bộ test suite của LeadHunter được tổ chức thành 3 nhóm rõ ràng:

```text
tests/
├── unit/                         # Unit tests cho từng module độc lập
│   ├── domain/                   # Test entities, value objects, services (Email, Phone, Telecom...)
│   ├── application/              # Test use cases (AutoRunUseCase, Export...)
│   ├── test_phase2_regression.py # Regression tests cho Bug 1, Bug 2, Bug 4
│   ├── test_db_duplicate_protection.py # Regression tests cho Bug 3 (Unique Index & Concurrency)
│   ├── test_massive_cases.py     # Parameterized stress tests (80 test cases)
│   └── test_stress_edge_cases.py # Stress test các trường hợp biên dữ liệu rác
└── integration/                  # Integration tests với SQLite CSDL thực
    ├── test_migration_runner.py  # Test quy trình chạy Migration 001, 002
    └── test_sqlite_repository.py # Test CRUD và lọc danh sách trong CSDL
```

---

## 🎯 2. DANH MỤC REGRESSION TESTS CHUYÊN SÂU

### 2.1. Bug 1 Regression (`TestBug1ConsecutiveZeroLeads`)
Xác minh bộ đếm `consecutive_zero_queries` được bảo vệ bằng `data_lock` đa luồng, trigger dừng 3s chính xác khi 3 query trả về 0 lead.

### 2.2. Bug 2 Regression (`TestBug2DynamicTargetOverflow`)
Xác minh khi ngành PCCC bị thiếu số, hệ thống không dừng luồng sớm mà tự động cào bù từ các ngành Xây dựng / Gara để chiến dịch đạt đủ `TARGET` tổng.

### 2.3. Bug 3 Regression (`TestSQLiteDuplicateProtection`)
Xác minh 5 thread insert đồng thời số điện thoại trùng lặp được CSDL chặn đứng qua `UNIQUE INDEX`, giữ số lượng bản ghi trong CSDL chính xác là 1.

### 2.4. Bug 4 Regression (`TestBug4GeographicFilter`)
Xác minh chấp nhận các định dạng địa chỉ `HCM`, `TP.HCM`, `Hồ Chí Minh`, `Sài Gòn`, `Dĩ An`, `Biên Hòa` và bác bỏ `Hà Nội`, `Cần Thơ`, `Long An`, `Việt Nam`.

---

## 🚀 3. LỆNH CHẠY KIỂM THỬ (TEST RUN COMMANDS)

```bash
# Chạy toàn bộ test suite
/home/acer/.local/bin/pytest tests/ -v

# Chạy riêng các regression test Phase 2
/home/acer/.local/bin/pytest tests/unit/test_phase2_regression.py tests/unit/test_db_duplicate_protection.py -v
```
