import re

with open("leadhunter/application/use_cases/auto_run_use_case.py", "r") as f:
    content = f.read()

# We need to replace the entire execute function's body from BƯỚC 1 down to BƯỚC 4
new_body = """        # Mục tiêu: đúng 80 lead sạch mỗi đợt
        TARGET = 80

        # ----------------------------------------------------------------
        # BƯỚC 1: Cào dữ liệu thô từ Google Maps (Thu thập đủ TARGET lead cho TỪNG TỪ KHÓA)
        # ----------------------------------------------------------------
        print(f"\\n🚀 Bắt đầu cào tự động cho các từ khóa: {keywords}", flush=True)

        for original_kw in keywords:
            leads_for_current_kw = 0
            queries_for_kw = _generate_queries(original_kw)
            
            for kw in queries_for_kw:
                if leads_for_current_kw >= TARGET:
                    break
                
                print(f"\\n🔍 [Đang cào Google Maps] Từ khóa: '{kw}' | Từ khóa gốc '{original_kw}' đã tích lũy: {leads_for_current_kw}/{TARGET} lead sạch...", flush=True)
                raw_leads = self._maps_scraper.scrape_fast(kw, min_clean_target=TARGET)
                logger.info(f"'{kw}' → {len(raw_leads)} kết quả thô từ Google Maps")

                # ----------------------------------------------------------------
                # BƯỚC 2: Lọc từng kết quả thô
                # ----------------------------------------------------------------
                for raw in raw_leads:
                    if leads_for_current_kw >= TARGET:
                        break

                    name_val = raw.get("company_name") or raw.get("name", "")
                    if not _is_valid_name(name_val):
                        continue

                    # Lọc: đã có website → bỏ qua
                    if _has_website(raw):
                        stats["has_web"] += 1
                        continue

                    # Lọc: không thuộc TP.HCM → bỏ qua
                    if not _is_in_hcm(raw.get("address", "")):
                        stats["not_hcm"] += 1
                        continue

                    # Lọc: SĐT không hợp lệ / Viettel / tổng đài → bỏ qua
                    valid, phone_vo = _is_valid_phone(raw.get("phone", ""))
                    if not valid:
                        stats["viettel"] += 1
                        continue

                    # Lọc: số trùng (trong đợt hoặc trong CSDL) → bỏ qua
                    if _is_duplicate(phone_vo.value, raw.get("company_name", ""), batch_phones, self._repository):
                        stats["dup"] += 1
                        continue

                    # Tạo entity Lead từ dữ liệu đã qua lọc
                    lead = _build_lead(raw, phone_vo, import_batch_id)
                    if not lead:
                        continue

                    # ----------------------------------------------------------------
                    # BƯỚC 3: Lưu lead hợp lệ vào Database
                    # ----------------------------------------------------------------
                    self._repository.add(lead)
                    batch_leads.append(lead)
                    batch_phones.add(phone_vo.value)
                    leads_for_current_kw += 1
                    print(f"  💾 [Đã lưu CSDL #{len(batch_leads)}] {lead.company_name} | SĐT: {lead.phone} | Địa chỉ: {lead.address[:35]}...", flush=True)

        logger.info(
            f"Hoàn tất | Thêm: {len(batch_leads)} | "
            f"Bỏ Viettel: {stats['viettel']} | "
            f"Bỏ có web: {stats['has_web']} | "
            f"Bỏ ngoài HCM: {stats['not_hcm']} | "
            f"Bỏ trùng: {stats['dup']}"
        )"""

# Find the start of "TARGET = 80"
start_idx = content.find("        TARGET = 80")
# Find the start of "        # BƯỚC 4: Xuất file Excel kết quả"
end_idx = content.find("        # ----------------------------------------------------------------\n        # BƯỚC 4: Xuất file Excel kết quả")

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + new_body + "\n\n" + content[end_idx:]
    with open("leadhunter/application/use_cases/auto_run_use_case.py", "w") as f:
        f.write(new_content)
    print("Fixed!")
else:
    print("Could not find boundaries!")
