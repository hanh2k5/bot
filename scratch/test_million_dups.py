import sys
import time
import tracemalloc

print("=" * 60)
print("🚀 BẮT ĐẦU BENCHMARK THỬ NGHỆM 1.000.000 (1 TRIỆU) SỐ TRÙNG CSDL")
print("=" * 60)

tracemalloc.start()

# 1. Nạp 1.000.000 SĐT vào RAM Set
start_load = time.time()
db_phones = {f"09{i:08d}" for i in range(1000000)}
load_time = time.time() - start_load

current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()

ram_used_mb = peak / (1024 * 1024)

print(f"✅ Nạp thành công {len(db_phones):,} số CSDL vào RAM!")
print(f"⏱️  Thời gian nạp toàn bộ 1 triệu số : {load_time:.4f} giây")
print(f"💾 RAM đỉnh tiêu tốn                   : {ram_used_mb:.2f} MB")

# 2. Thử nghiệm tra cứu trùng lặp 100.000 lượt ngẫu nhiên
print("\n" + "-" * 60)
print("🔍 THỬ NGHIỆM TRA CỨU TRÙNG 100.000 LẦN TẬN GỐC (LOOKUP BENCHMARK)")
print("-" * 60)

test_phones = [f"09{i:08d}" for i in range(50000, 150000)] # 100,000 số có trùng

start_lookup = time.time()
dup_count = 0
for p in test_phones:
    if p in db_phones:
        dup_count += 1
lookup_time = time.time() - start_lookup

avg_microseconds = (lookup_time / len(test_phones)) * 1000000

print(f"🎯 Số lượt phát hiện trùng         : {dup_count:,} / {len(test_phones):,}")
print(f"⏱️  Tổng thời gian check 100.000 lần : {lookup_time:.6f} giây")
print(f"⚡ Thời gian check MỖI SỐ          : {avg_microseconds:.4f} microgiây (0.00000{int(avg_microseconds)}s)")
print("=" * 60)
