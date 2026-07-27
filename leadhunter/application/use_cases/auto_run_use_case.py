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
    other_provinces = ["hà nội", "đà nẵng", "hải phòng", "cần thơ", "đồng nai", "bình dương", "long an"]
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
    """Trả về chính xác từ khóa người dùng nhập (không tự đẻ thêm từ khóa rác)."""
    return [kw.lower().strip()]


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

    def execute(self, keywords: list[str]) -> dict[str, int | str]:
        """Chạy pipeline cào lead cho danh sách từ khóa.

        Args:
            keywords: Danh sách từ khóa tìm kiếm (vd: ["quán cafe", "spa"]).

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

        # Mục tiêu: đúng 80 lead sạch mỗi đợt
        # Mục tiêu: đúng 80 lead sạch mỗi đợt
        # Mục tiêu: đúng 80 lead sạch mỗi đợt
        TARGET = 80

        # ----------------------------------------------------------------
        # BƯỚC 1: Cào dữ liệu thô từ Google Maps (Thu thập đủ TARGET lead TỔNG CỘNG)
        # ----------------------------------------------------------------
        print(f"\n🚀 Bắt đầu cào tự động cho các từ khóa: {keywords}", flush=True)

        for original_kw in keywords:
            if len(batch_leads) >= TARGET:
                break
            
            queries_for_kw = _generate_queries(original_kw)
            for kw in queries_for_kw:
                if len(batch_leads) >= TARGET:
                    break
                print(f"\n🔍 [Đang cào Google Maps] Từ khóa: '{kw}' | Đã tích lũy: {len(batch_leads)}/{TARGET} lead sạch...", flush=True)
                raw_leads = self._maps_scraper.scrape_fast(kw, min_clean_target=TARGET)
                logger.info(f"'{kw}' → {len(raw_leads)} kết quả thô từ Google Maps")

                # ----------------------------------------------------------------
                # BƯỚC 2: Lọc từng kết quả thô
                # ----------------------------------------------------------------
                for raw in raw_leads:
                    if len(batch_leads) >= TARGET:
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
                    print(f"  💾 [Đã lưu CSDL #{len(batch_leads)}] {lead.company_name} | SĐT: {lead.phone} | Địa chỉ: {lead.address[:35]}...", flush=True)

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
