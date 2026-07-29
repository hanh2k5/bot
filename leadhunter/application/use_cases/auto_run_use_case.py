"""AutoRunUseCase — Application layer.

Điều phối toàn bộ quy trình cào lead tự động hàng ngày:
  1. Cào dữ liệu thô từ Google Maps.
  2. Lọc (HCM, SĐT hợp lệ, không Viettel, không có website, không trùng).
  3. Lưu vào Database.
  4. Xuất file Excel.
"""

from __future__ import annotations

import logging
import uuid
import time
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from leadhunter.application.ports.lead_repository import LeadRepository
    from leadhunter.infrastructure.adapters.google_maps_scraper import GoogleMapsScraper
    from leadhunter.application.use_cases.export_leads_to_excel import ExportLeadsToExcelUseCase

from leadhunter.domain.entities.lead import Lead, LeadStatus
from leadhunter.domain.services.telecom_service import is_viettel, is_tong_dai
from leadhunter.domain.services.normalization_service import (
    normalize_address,
    normalize_company_name,
    normalize_phone,
)
from leadhunter.application.dtos import ExportParamsDTO

logger = logging.getLogger(__name__)

# Danh sách từ khoá để xác nhận địa chỉ thuộc TP.HCM
_HCM_KEYWORDS = [
    "hồ chí minh", "ho chi minh", "hcm", "tphcm", "tp.hcm", "tp hcm",
    "quận 1", "quận 2", "quận 3", "quận 4", "quận 5", "quận 6", "quận 7", "quận 8", "quận 9", "quận 10", "quận 11", "quận 12",
    "tân bình", "gò vấp", "bình thạnh", "phú nhuận", "tân phú", "bình tân", "thủ đức", "hóc môn", "củ chi", "nhà bè", "cần giờ",
    "việt nam", "vietnam"
]


# ---------------------------------------------------------------------------
# Các hàm lọc độc lập (DRY — mỗi hàm 1 nhiệm vụ duy nhất)
# ---------------------------------------------------------------------------

def _is_in_hcm(address: str) -> bool:
    """Kiểm tra địa chỉ có thuộc HCM không."""
    if not address or len(address.strip()) < 5:
        # Nếu không trích xuất được địa chỉ nhưng search theo quận HCM thì vẫn tin cậy
        return True
        
    # Loại bỏ các địa chỉ "giả" (Plus Codes) như: 4HW7+54G, Ấp kiến An...
    import re
    if re.match(r"^[A-Z0-9]{2,4}\+[A-Z0-9]{2,3}", address.strip()):
        return False

    a = address.lower()
    if "hồ chí minh" in a or "ho chi minh" in a or "hcm" in a or "tphcm" in a or "tp.hcm" in a:
        return True
        
    hcm_districts = [
        "quận 1", "quận 2", "quận 3", "quận 4", "quận 5", "quận 6", "quận 7", "quận 8", "quận 9", "quận 10",
        "quận 11", "quận 12", "tân bình", "bình tân", "tân phú", "phú nhuận", "gò vấp", "bình thạnh",
        "thủ đức", "nhà bè", "hóc môn", "củ chi", "bình chánh", "cần giờ"
    ]
    if any(d in a for d in hcm_districts):
        return True
        
    # Vẫn cho qua nếu địa chỉ không chứa từ khóa tỉnh khác
    other_provinces = ["hà nội", "ha noi", "đà nẵng", "da nang", "hải phòng", "hai phong", "cần thơ", "can tho", "đồng nai", "dong nai", "bình dương", "binh duong", "long an"]
    if any(p in a for p in other_provinces):
        return False
        
    return True


def _has_website(raw: dict) -> bool:
    """Trả về True nếu đơn vị đã có website (không phải mục tiêu bán dịch vụ)."""
    return bool(raw.get("website", "").strip())


_JUNK_UI_BUTTONS = {
    "see nearby", "see similar places", "similar places", "directions", "overview", "reviews",
    "restroom", "gender-neutral restroom", "paid street parking", "street parking", "parking",
    "education center", "training center", "photo", "recycling", "payments",
    "claim this business", "debit cards", "open 24 hours", "full restoration service",
    "checks", "accessible entrance", "wheelchair"
}

def _is_valid_name(name: str) -> bool:
    """Kiểm tra tên có hợp lệ (loại bỏ nút bấm UI, Place ID, mã hash ngẫu nhiên)."""
    if not name or len(name.strip()) < 2:
        return False
    if all(not c.isalpha() for c in name):
        return False
    nm_clean = name.strip()
    nm_lower = nm_clean.lower()
    if "|" in nm_clean or nm_clean.startswith("0a") or nm_clean.startswith("ChI") or nm_clean.startswith("0x") or nm_clean.startswith("CIH"):
        return False
    if " " not in nm_clean and len(nm_clean) >= 7:
        has_upper = any(c.isupper() for c in nm_clean)
        has_lower = any(c.islower() for c in nm_clean)
        has_digit = any(c.isdigit() or c in "-_" for c in nm_clean)
        if (has_upper and has_lower) or has_digit:
            return False
    if any(u in nm_lower for u in _JUNK_UI_BUTTONS):
        return False
    return True


def _is_valid_phone(phone_raw: str) -> tuple[bool, object | None]:
    """Chuẩn hóa SĐT và kiểm tra hợp lệ (không Viettel, không tổng đài).

    Returns:
        (True, phone_vo)  — nếu SĐT hợp lệ.
        (False, None)     — nếu SĐT không hợp lệ hoặc cần bỏ qua.
    """
    if not phone_raw:
        return False, None

    phone_vo = normalize_phone(phone_raw)
    if not phone_vo or not phone_vo.value:
        return False, None

    if is_tong_dai(phone_vo.value):
        return False, None

    if is_viettel(phone_vo.value):
        return False, None

    return True, phone_vo


def _is_duplicate(
    phone_value: str,
    company_name: str,
    batch_seen_phones: set[str],
    repository: "LeadRepository",
) -> bool:
    """Kiểm tra SĐT đã tồn tại chưa (trong đợt hiện tại hoặc trong CSDL lịch sử).

    DRY: gom 2 bước kiểm tra trùng thành 1 hàm duy nhất.
    """
    # Trùng trong cùng đợt cào hôm nay
    if phone_value in batch_seen_phones:
        return True

    # Trùng với CSDL lịch sử từ trước đến nay
    dups = repository.find_duplicates(company_name=company_name.lower(), phone=phone_value)
    return bool(dups)


def _build_lead(raw: dict, phone_vo, import_batch_id: str) -> Lead | None:
    """Tạo entity Lead từ dữ liệu thô.

    Returns:
        Lead entity nếu thành công, None nếu tên công ty không hợp lệ.
    """
    try:
        company_vo = normalize_company_name(raw.get("company_name", ""))
    except Exception:
        return None

    return Lead(
        company_name=company_vo.value,
        contact_name="",
        email="",
        phone=phone_vo.value,
        website="",
        address=normalize_address(raw.get("address", "")),
        source=raw.get("source", "google_maps"),
        source_reference=raw.get("source_reference", ""),
        status=LeadStatus.NEW,
        import_batch_id=import_batch_id,
        phone_normalized=phone_vo.normalized,
    )


# ---------------------------------------------------------------------------
# Use Case chính
# ---------------------------------------------------------------------------

def _generate_queries(kw: str) -> list[str]:
    """Nếu người dùng nhập từ khóa chung chung, tự động thêm các quận HCM để quét được nhiều số hơn."""
    base_kw = kw.lower().strip()
    
    # Nếu từ khóa đã có chữ "quận", "huyện", "thủ đức", "hcm" thì không thêm nữa
    if any(x in base_kw for x in ["quận", "huyện", "q1", "q2", "q3", "thủ đức", "hcm", "hồ chí minh"]):
        return [base_kw]

    hcm_districts = [
        "Quận 1", "Quận 2", "Quận 3", "Quận 4", "Quận 5", "Quận 6", "Quận 7", "Quận 8", 
        "Quận 9", "Quận 10", "Quận 11", "Quận 12", "Tân Bình", "Gò Vấp", "Bình Thạnh", 
        "Phú Nhuận", "Tân Phú", "Bình Tân", "Thủ Đức", "Hóc Môn", "Củ Chi", "Nhà Bè", "Bình Chánh"
    ]
    return [f"{base_kw} {dist}" for dist in hcm_districts]


# ---------------------------------------------------------------------------
# Use Case chính
# ---------------------------------------------------------------------------

class AutoRunUseCase:
    """Điều phối quy trình cào lead tự động hàng ngày."""

    def __init__(
        self,
        repository: "LeadRepository",
        maps_scraper: "GoogleMapsScraper",
        export_use_case: "ExportLeadsToExcelUseCase",
    ) -> None:
        self._repository = repository
        self._maps_scraper = maps_scraper
        self._export_use_case = export_use_case

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def execute(self, keywords: list[str], target: int = 80) -> dict[str, int | str]:
        """Chạy pipeline cào lead cho danh sách từ khóa.

        Args:
            keywords: Danh sách từ khóa tìm kiếm (vd: ["quán cafe", "spa"]).
            target: Số lượng lead hợp lệ cần thu thập.

        Returns:
            Dict tổng hợp kết quả: số lead thêm, thống kê bỏ qua, đường dẫn file xuất.
        """
        import_batch_id = str(uuid.uuid4())
        logger.info(f"Bắt đầu đợt cào mới | Mã đợt: {import_batch_id}")

        # Bộ đếm thống kê để hiển thị kết quả cuối
        stats = {"viettel": 0, "has_web": 0, "not_hcm": 0, "dup": 0}

        # Danh sách lead hợp lệ thu được trong đợt này
        batch_leads: list[Lead] = []
        # Tập SĐT đã thấy trong đợt này (tránh trùng nội bộ)
        batch_phones: set[str] = set()

        TARGET = target

        # ----------------------------------------------------------------
        # BƯỚC 1: Cào dữ liệu thô từ Google Maps (Thu thập đủ TARGET lead TỔNG CỘNG)
        # ----------------------------------------------------------------
        print(f"\n[*] Khởi động tìm kiếm phân bổ đều: {keywords} bằng 3 Nhân Đa Luồng", flush=True)

        print_lock = threading.Lock()
        data_lock = threading.Lock()
        stop_event = threading.Event()

        def _print_status(status_text: str, current_count: int = -1, worker_id: int = 1):
            with print_lock:
                display_count = len(batch_leads)
                if display_count >= TARGET:
                    display_count = TARGET
                
                p = int((display_count / TARGET) * 100) if TARGET > 0 else 100
                t_len = 20
                pos = int((display_count / TARGET) * t_len) if TARGET > 0 else t_len
                if pos > t_len: pos = t_len
                
                bird_segment = f"🏍︎({display_count}/{TARGET})"
                left_dashes = "-" * pos
                right_dashes = "-" * (t_len - pos)
                
                b = f"\033[1m0%\033[0m \033[95m{left_dashes}{bird_segment}{right_dashes}>\033[0m \033[1m100%\033[0m"
                # Chỉ in các log hệ thống, ẨN các log dữ liệu cào/bỏ qua theo ý sếp
                sys.stdout.write("\033[2K\r")
                if status_text and not any(x in status_text for x in ["Chốt đơn", "Bỏ qua", "Tìm thấy", "ĐÃ TÌM THẤY", "ĐÃ LẤY"]):
                    if "✅" in status_text: status_text = f"\033[92m{status_text}\033[0m"
                    elif "❌" in status_text: status_text = f"\033[90m{status_text}\033[0m"
                    elif "⚠️" in status_text: status_text = f"\033[93m{status_text}\033[0m"
                    elif "🔄" in status_text: status_text = f"\033[96m{status_text}\033[0m"
                    elif "🔍" in status_text: status_text = f"\033[94m{status_text}\033[0m"
                    sys.stdout.write(f"  {status_text}\n")

                sys.stdout.write(f"  {b}\r")
                sys.stdout.flush()

        def dup_check_fn(p: str, n: str):
            with data_lock:
                return _is_duplicate(p, n, batch_phones, self._repository)

        # Tính chỉ tiêu cho từng từ khóa (chia đều, phần dư cộng vào các từ khóa đầu)
        targets_by_kw = {}
        counts_by_kw = {}
        if TARGET > 0 and len(keywords) > 0:
            base_tgt = TARGET // len(keywords)
            rem_tgt = TARGET % len(keywords)
            for i, kw in enumerate(keywords):
                targets_by_kw[kw] = base_tgt + (1 if i < rem_tgt else 0)
                counts_by_kw[kw] = 0
        else:
            for kw in keywords:
                targets_by_kw[kw] = 999999
                counts_by_kw[kw] = 0

        all_queries = []
        for original_kw in keywords:
            for q in _generate_queries(original_kw):
                all_queries.append((original_kw, q))

        def _worker_task(original_kw: str, kw: str, worker_id: int):
            with data_lock:
                if len(batch_leads) >= TARGET:
                    return
                if counts_by_kw[original_kw] >= targets_by_kw[original_kw]:
                    return
            
            _print_status(f"🔄 [Nhân {worker_id}] Bắt đầu quét: '{kw}'", worker_id=worker_id)
            
            raw_leads = self._maps_scraper.scrape_fast(
                kw, 
                min_clean_target=30, # Mỗi từ khóa lấy tối đa 30 kết quả thô, chia đều cho các quận
                status_callback=lambda msg, c: _print_status(msg, c, worker_id),
                is_duplicate_fn=dup_check_fn,
                worker_id=worker_id,
                stop_event=stop_event
            )
            
            logger.info(f"[Nhân {worker_id}] '{kw}' → {len(raw_leads)} kết quả thô")

            for raw in raw_leads:
                with data_lock:
                    if len(batch_leads) >= TARGET:
                        stop_event.set()
                        return
                    if counts_by_kw[original_kw] >= targets_by_kw[original_kw]:
                        return

                time.sleep(0.1)  # Giảm delay vì chạy đa luồng

                name_val = raw.get("company_name") or raw.get("name", "")
                if not _is_valid_name(name_val):
                    continue

                if _has_website(raw):
                    with data_lock: stats["has_web"] += 1
                    _print_status(f"❌ [Nhân {worker_id}] Bỏ qua: {name_val[:20]} (Website)")
                    continue

                if not _is_in_hcm(raw.get("address", "")):
                    with data_lock: stats["not_hcm"] += 1
                    _print_status(f"❌ [Nhân {worker_id}] Bỏ qua: {name_val[:20]} (Ngoài HCM)")
                    continue

                valid, phone_vo = _is_valid_phone(raw.get("phone", ""))
                if not valid:
                    with data_lock: stats["viettel"] += 1
                    _print_status(f"❌ [Nhân {worker_id}] Bỏ qua: {name_val[:20]} (Số rác/Viettel)")
                    continue

                with data_lock:
                    if len(batch_leads) >= TARGET:
                        stop_event.set()
                        return
                    if counts_by_kw[original_kw] >= targets_by_kw[original_kw]:
                        return
                        
                    if _is_duplicate(phone_vo.value, raw.get("company_name", ""), batch_phones, self._repository):
                        stats["dup"] += 1
                        _print_status(f"❌ [Nhân {worker_id}] Bỏ qua: {name_val[:20]} (Trùng lặp)")
                        continue

                    lead = _build_lead(raw, phone_vo, import_batch_id)
                    if not lead:
                        continue

                    self._repository.add(lead)
                    batch_leads.append(lead)
                    batch_phones.add(phone_vo.value)
                    counts_by_kw[original_kw] += 1
                    _print_status(f"✅ [Nhân {worker_id}] Chốt đơn: {lead.company_name[:20]} | {lead.phone}")

        # Chạy 3 luồng song song theo yêu cầu của user
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for idx, kw in enumerate(all_queries):
                worker_id = (idx % 3) + 1
                original_kw, q_str = kw
                futures.append(executor.submit(_worker_task, original_kw, q_str, worker_id))
            
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Lỗi ở worker: {e}")
                
                with data_lock:
                    if len(batch_leads) >= TARGET:
                        stop_event.set()
                        executor.shutdown(wait=False, cancel_futures=True)
                        break

        print("\n\n") # Xuống dòng khi kết thúc để giữ thanh tiến trình

        logger.info(
            f"Hoàn tất | Thêm: {len(batch_leads)} | "
            f"Bỏ Viettel: {stats['viettel']} | "
            f"Bỏ có web: {stats['has_web']} | "
            f"Bỏ ngoài HCM: {stats['not_hcm']} | "
            f"Bỏ trùng: {stats['dup']}"
        )

        # ----------------------------------------------------------------
        # BƯỚC 4: Xuất file Excel kết quả
        # ----------------------------------------------------------------
        export_file = self._export(batch_leads)

        return {
            "batch_id": import_batch_id,
            "added_count": len(batch_leads),
            "skipped_viettel": stats["viettel"],
            "skipped_has_website": stats["has_web"],
            "skipped_not_hcm": stats["not_hcm"],
            "skipped_duplicate": stats["dup"],
            "export_file": export_file,
        }

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _export(self, leads: list[Lead]) -> str:
        """Xuất CHÍNH XÁC đợt lead mới vừa cào được ra file Excel (nguon 1.xlsx, nguon 2.xlsx...).

        Không in lại các lead cũ đã có trong CSDL để dễ quản lý.
        """
        if not leads:
            return ""
        try:
            from pathlib import Path
            export_dir = Path("exports")
            export_dir.mkdir(parents=True, exist_ok=True)

            i = 1
            while (export_dir / f"nguon {i}.xlsx").exists():
                i += 1
            out_path = export_dir / f"nguon {i}.xlsx"

            excel_writer = getattr(self._export_use_case, "_excel_writer", None)
            if excel_writer:
                excel_writer.write(leads, str(out_path))
            else:
                from leadhunter.infrastructure.adapters.excel_writer_adapter import ExcelWriterAdapter
                ExcelWriterAdapter().write(leads, str(out_path))

            logger.info(f"Đã xuất {len(leads)} lead mới vào file: {out_path}")
            return str(out_path)
        except Exception as exc:
            logger.error(f"Lỗi xuất file Excel: {exc}")
            return ""
