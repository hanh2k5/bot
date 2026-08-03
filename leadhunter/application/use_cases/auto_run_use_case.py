"""AutoRunUseCase — Application layer.

Điều phối toàn bộ quy trình cào lead tự động hàng ngày:
  1. Cào dữ liệu thô từ Google Maps.
  2. Lọc (HCM, SĐT hợp lệ, không Viettel, không có website, không trùng, tên phải khớp từ khóa).
  3. Lưu vào Database.
  4. Xuất file Excel.
"""

from __future__ import annotations

import logging
import uuid
import time
import sys
import threading
import signal
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from leadhunter.application.ports.lead_repository import LeadRepository
    from leadhunter.infrastructure.adapters.google_maps_scraper import GoogleMapsScraper
    from leadhunter.application.use_cases.export_leads_to_excel import (
        ExportLeadsToExcelUseCase,
    )

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
    "hồ chí minh",
    "ho chi minh",
    "hcm",
    "tphcm",
    "tp.hcm",
    "tp hcm",
    "quận 1",
    "quận 2",
    "quận 3",
    "quận 4",
    "quận 5",
    "quận 6",
    "quận 7",
    "quận 8",
    "quận 9",
    "quận 10",
    "quận 11",
    "quận 12",
    "tân bình",
    "gò vấp",
    "bình thạnh",
    "phú nhuận",
    "tân phú",
    "bình tân",
    "thủ đức",
    "hóc môn",
    "củ chi",
    "nhà bè",
    "cần giờ",
    "việt nam",
    "vietnam",
]


# ---------------------------------------------------------------------------
# Các hàm lọc độc lập (DRY — mỗi hàm 1 nhiệm vụ duy nhất)
# ---------------------------------------------------------------------------


def _is_in_hcm(address: str) -> bool:
    """Kiểm tra địa chỉ CHÍNH QUY thuộc Tam Giác Vàng: HCM, Bình Dương, Đồng Nai."""
    # SỬA LỖI 1: Địa chỉ rỗng hoặc quá ngắn -> Chặn (False)
    if not address or len(address.strip()) < 5:
        return False

    import re

    if re.match(r"^[A-Z0-9]{2,4}\+[A-Z0-9]{2,3}", address.strip()):
        return False

    a = address.lower()

    # DANH SÁCH DUY NHẤT ĐƯỢC PHÉP QUA CỬA
    valid_provinces = [
        "hồ chí minh",
        "hcm",
        "tphcm",
        "bình dương",
        "binh duong",
        "đồng nai",
        "dong nai",
        "biên hòa",
        "dĩ an",
        "thuận an",
        "thủ dầu một",
        "long thành",
        "nhơn trạch",
        "trảng bom",
        "bến cát",
        "tân uyên",
        "long khánh",
        "bàu bàng",
        "cẩm mỹ",
        "sài gòn",
    ]

    if any(p in a for p in valid_provinces):
        return True

    # SỬA LỖI 2: Không nằm trong danh sách trên -> Chặn đứng (False)
    return False


def _has_website(raw: dict) -> bool:
    """Trả về True nếu đơn vị đã có website."""
    return bool(raw.get("website", "").strip())


_JUNK_UI_BUTTONS = {
    "see nearby",
    "see similar places",
    "similar places",
    "directions",
    "overview",
    "reviews",
    "restroom",
    "gender-neutral restroom",
    "paid street parking",
    "street parking",
    "parking",
    "education center",
    "training center",
    "photo",
    "recycling",
    "payments",
    "claim this business",
    "debit cards",
    "open 24 hours",
    "full restoration service",
    "checks",
    "accessible entrance",
    "wheelchair",
}


def _is_valid_name(name: str) -> bool:
    """Kiểm tra tên có hợp lệ (loại bỏ nút bấm UI, Place ID, mã hash ngẫu nhiên)."""
    if not name or len(name.strip()) < 2:
        return False
    if all(not c.isalpha() for c in name):
        return False
    nm_clean = name.strip()
    nm_lower = nm_clean.lower()
    if (
        "|" in nm_clean
        or nm_clean.startswith("0a")
        or nm_clean.startswith("ChI")
        or nm_clean.startswith("0x")
        or nm_clean.startswith("CIH")
    ):
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


def _is_valid_phone(phone_raw: str, allow_viettel: bool = False) -> tuple[bool, object | None]:
    """Chuẩn hóa SĐT và kiểm tra hợp lệ (không Viettel nếu allow_viettel=False, không tổng đài)."""
    if not phone_raw:
        return False, None

    phone_vo = normalize_phone(phone_raw)
    if not phone_vo or not phone_vo.value:
        return False, None

    if is_tong_dai(phone_vo.value):
        return False, None

    if not allow_viettel and is_viettel(phone_vo.value):
        return False, None

    return True, phone_vo


def _is_duplicate(
    phone_value: str,
    company_name: str,
    batch_seen_phones: set[str],
    repository: "LeadRepository",
) -> bool:
    """Kiểm tra SĐT đã tồn tại chưa (trong đợt hiện tại hoặc trong CSDL lịch sử)."""
    if phone_value in batch_seen_phones:
        return True

    dups = repository.find_duplicates(
        company_name=company_name.lower(), phone=phone_value
    )
    return bool(dups)


def _build_lead(raw: dict, phone_vo, import_batch_id: str) -> Lead | None:
    """Tạo entity Lead từ dữ liệu thô."""
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
    """Tự động rải quân đều khắp 3 vùng: HCM, Bình Dương, Đồng Nai."""
    base_kw = f'"{kw.lower().strip()}"'

    if any(
        x in base_kw
        for x in [
            "quận",
            "huyện",
            "thành phố",
            "hcm",
            "bình dương",
            "đồng nai",
            "biên hòa",
            "dĩ an",
        ]
    ):
        return [base_kw]

    locations = [
        "Quận 1",
        "Biên Hòa",
        "Dĩ An",
        "Quận 7",
        "Thuận An",
        "Long Thành",
        "Quận 9",
        "Thủ Dầu Một",
        "Trảng Bom",
        "Tân Bình",
        "Bến Cát",
        "Nhơn Trạch",
        "Gò Vấp",
        "Tân Uyên",
        "Long Khánh",
        "Thủ Đức",
        "Bàu Bàng",
        "Cẩm Mỹ",
        "Bình Thạnh",
        "Quận 10",
        "Quận 12",
    ]
    return [f"{base_kw} {loc}" for loc in locations]


# Bắt sự kiện Ctrl + C để dừng khẩn cấp lập tức (đặt sát lề trái, ngoài class)
def _signal_handler(sig, frame):
    try:
        sys.stdout.write("\n🛑 [STOP] Đã nhận lệnh hủy (Ctrl+C), đang dọn dẹp và thoát êm...\n")
        sys.stdout.flush()
    except Exception:
        pass

    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        os.close(devnull)
    except Exception:
        pass

    try:
        os.killpg(os.getpgrp(), signal.SIGKILL)
    except Exception:
        os._exit(0)


# Đăng ký tín hiệu
signal.signal(signal.SIGINT, _signal_handler)


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

    def execute(
        self,
        keywords: list[str],
        target: int = 80,
        allow_viettel: bool = False,
        allow_web: bool = False,
    ) -> dict[str, int | str]:

        import_batch_id = str(uuid.uuid4())
        logger.info(f"Bắt đầu đợt cào mới | Mã đợt: {import_batch_id}")

        stats = {"viettel": 0, "has_web": 0, "not_hcm": 0, "dup": 0}
        batch_leads: list[Lead] = []
        batch_phones: set[str] = set()
        TARGET = target

        print(
            f"\n[*] Khởi động tìm kiếm phân bổ đều: {keywords} bằng 3  Đa Luồng",
            flush=True,
        )

        print_lock = threading.Lock()
        data_lock = threading.Lock()
        stop_event = threading.Event()

        # 🛑 CHIA ĐỀU CHỈ TIÊU CHO TỪNG TỪ KHÓA (Ví dụ 80 cho 3 từ -> 27, 27, 26)
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

        def _print_status(
            status_text: str, current_count: int = -1, worker_id: int = 1
        ):
            with print_lock:
                display_count = len(batch_leads)
                if display_count >= TARGET:
                    display_count = TARGET

                p = int((display_count / TARGET) * 100) if TARGET > 0 else 100
                t_len = 20
                pos = int((display_count / TARGET) * t_len) if TARGET > 0 else t_len
                if pos > t_len:
                    pos = t_len

                bird_segment = f" ✈︎ ({display_count}/{TARGET})"
                left_dashes = "-" * pos
                right_dashes = "-" * (t_len - pos)

                b = f"\033[1m0%\033[0m \033[95m{left_dashes}{bird_segment}{right_dashes}>\033[0m \033[1m100%\033[0m"
                sys.stdout.write("\033[2K\r")
                if status_text and not any(
                    x in status_text
                    for x in ["Chốt đơn", "Bỏ qua", "Tìm thấy", "ĐÃ TÌM THẤY", "ĐÃ LẤY"]
                ):
                    if "✅" in status_text:
                        status_text = f"\033[92m{status_text}\033[0m"
                    elif "❌" in status_text:
                        status_text = f"\033[90m{status_text}\033[0m"
                    elif "⚠️" in status_text:
                        status_text = f"\033[93m{status_text}\033[0m"
                    elif "🔄" in status_text:
                        status_text = f"\033[96m{status_text}\033[0m"
                    elif "🔍" in status_text:
                        status_text = f"\033[94m{status_text}\033[0m"
                    sys.stdout.write(f"  {status_text}\n")

                sys.stdout.write(f"  {b}\r")
                sys.stdout.flush()

        def dup_check_fn(p: str, n: str):
            with data_lock:
                return _is_duplicate(p, n, batch_phones, self._repository)

        def _worker_task(original_kw: str, kw: str, worker_id: int):
            with data_lock:
                # 🛑 FIX 1: Dừng nếu đạt chỉ tiêu của riêng ngành này HOẶC đạt chỉ tiêu tổng
                if (
                    len(batch_leads) >= TARGET
                    or counts_by_kw[original_kw] >= targets_by_kw[original_kw]
                ):
                    return

            os_names = ["Linux", "Mac", "Win"]
            os_name = os_names[(worker_id - 1) % len(os_names)]

            _print_status(f"🔄 [ {os_name}] Bắt đầu quét: '{kw}'", worker_id=worker_id)

            raw_leads = self._maps_scraper.scrape_fast(
                kw,
                min_clean_target=25,
                status_callback=lambda msg, c: _print_status(msg, c, worker_id),
                is_duplicate_fn=dup_check_fn,
                worker_id=worker_id,
                stop_event=stop_event,
            )

            logger.info(f"[ {worker_id}] '{kw}' → {len(raw_leads)} kết quả thô")

            query_tokens = [
                t.lower() for t in original_kw.split() if len(t.strip()) > 1
            ]

            for raw in raw_leads:
                with data_lock:
                    if (
                        len(batch_leads) >= TARGET
                        or counts_by_kw[original_kw] >= targets_by_kw[original_kw]
                    ):
                        stop_event.set()
                        return

                time.sleep(0.1)

                name_val = raw.get("company_name") or raw.get("name", "")
                if not _is_valid_name(name_val):
                    continue

                lower_name = name_val.lower()

                if query_tokens:
                    meaningful_tokens = [
                        t
                        for t in query_tokens
                        if t not in ["của", "va", "các", "cho", "tại", "tp"]
                    ]
                    if meaningful_tokens:
                        if not any(token in lower_name for token in meaningful_tokens):
                            with data_lock:
                                stats["not_hcm"] += 1
                            continue

                if not allow_web and _has_website(raw):
                    with data_lock:
                        stats["has_web"] += 1
                    continue

                if not _is_in_hcm(raw.get("address", "")):
                    with data_lock:
                        stats["not_hcm"] += 1
                    continue

                valid, phone_vo = _is_valid_phone(raw.get("phone", ""), allow_viettel=allow_viettel)
                if not valid:
                    with data_lock:
                        stats["viettel"] += 1
                    continue

                with data_lock:
                    if (
                        len(batch_leads) >= TARGET
                        or counts_by_kw[original_kw] >= targets_by_kw[original_kw]
                    ):
                        stop_event.set()
                        return

                    if _is_duplicate(
                        phone_vo.value,
                        raw.get("company_name", ""),
                        batch_phones,
                        self._repository,
                    ):
                        stats["dup"] += 1
                        continue

                    lead = _build_lead(raw, phone_vo, import_batch_id)
                    if not lead:
                        continue

                    if not lead.address or len(lead.address.strip()) < 10:
                        stats["not_hcm"] += 1
                        continue

                    batch_leads.append(lead)
                    batch_phones.add(phone_vo.value)
                    # 🛑 FIX 2: Cộng điểm vào đúng ngành đang cào để theo dõi phân bổ
                    counts_by_kw[original_kw] += 1

        # 🛑 CHẠY TUẦN TỰ TỪNG NGÀNH ĐỂ GOM KẾT QUẢ THEO KHỐI TỪ TRÊN XUỐNG DƯỚI
        import random

        for kw in keywords:
            if len(batch_leads) >= TARGET:
                break

            queries = _generate_queries(kw)
            random.shuffle(queries)

            print(
                f"\n[*] Đang cào khối ngành: '{kw}' (Mục tiêu: {targets_by_kw[kw]} số)...",
                flush=True,
            )

            all_queries = [(kw, q) for q in queries]

            # 🛑 FIX 3: Chuyển sang ngành mới phải reset cờ báo dừng
            stop_event.clear()

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = []
                for idx, q_tuple in enumerate(all_queries):
                    worker_id = (idx % 3) + 1
                    original_kw, q_str = q_tuple
                    futures.append(
                        executor.submit(_worker_task, original_kw, q_str, worker_id)
                    )

                for future in as_completed(futures):
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"Lỗi ở worker: {e}")

                    with data_lock:
                        # 🛑 FIX 4: Break đúng theo chỉ tiêu từng khối ngành
                        if (
                            counts_by_kw[kw] >= targets_by_kw[kw]
                            or len(batch_leads) >= TARGET
                        ):
                            stop_event.set()
                            executor.shutdown(wait=False, cancel_futures=True)
                            break

        print("\n\n")

        logger.info(
            f"Hoàn tất | Thêm: {len(batch_leads)} | "
            f"Bỏ Viettel: {stats['viettel']} | "
            f"Bỏ có web: {stats['has_web']} | "
            f"Bỏ ngoài HCM: {stats['not_hcm']} | "
            f"Bỏ trùng: {stats['dup']}"
        )

        # ----------------------------------------------------------------
        # BƯỚC 3.5: LƯU TỪNG LEAD VÀO DATABASE MỘT CÁCH AN TOÀN
        # ----------------------------------------------------------------
        if batch_leads:
            saved_count = 0
            for lead in batch_leads:
                try:
                    self._repository.add(lead)
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Lỗi khi lưu lead {lead.phone}: {e}")
            logger.info(
                f"Đã lưu thành công {saved_count}/{len(batch_leads)} lead vào Database."
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

    def _export(self, leads: list[Lead]) -> str:
        if not leads:
            return ""
        try:
            from pathlib import Path

            project_root = Path(__file__).resolve().parents[3]
            export_dir = project_root / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)

            i = 1
            while (export_dir / f"nguon {i}.xlsx").exists():
                i += 1
            out_path = export_dir / f"nguon {i}.xlsx"

            excel_writer = getattr(self._export_use_case, "_excel_writer", None)
            if excel_writer:
                excel_writer.write(leads, str(out_path))
            else:
                from leadhunter.infrastructure.adapters.excel_writer_adapter import (
                    ExcelWriterAdapter,
                )

                ExcelWriterAdapter().write(leads, str(out_path))

            logger.info(f"Đã xuất {len(leads)} lead mới vào file: {out_path}")
            return str(out_path)
        except Exception as exc:
            logger.error(f"Lỗi xuất file Excel: {exc}")
            return ""
