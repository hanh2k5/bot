"""Dịch vụ Kiểm tra & Lọc Nhà mạng Viễn thông (Telecom Service).

Cung cấp các hàm kiểm tra SĐT di động cá , lọc số Viettel, lọc số tổng đài 1900/1800, máy bàn 02x.
"""

from __future__ import annotations

import re
from typing import Final

# Danh sách đầu số Viettel & Phụ (bao gồm 032-039, 086, 087, 096, 097, 098, 056, 058, 052, 055, 059, 092)
_VIETTEL_3DIGITS: Final[frozenset[str]] = frozenset(
    {
        "096",
        "097",
        "098",
        "086",
        "087",
        "032",
        "033",
        "034",
        "035",
        "036",
        "037",
        "038",
        "039",
        "056",
        "058",
        "052",
        "055",
        "059",
        "092",
        "099",
    }
)


_VINAPHONE_3DIGITS: Final[frozenset[str]] = frozenset(
    {"081", "082", "083", "084", "085", "088", "091", "094"}
)

_MOBIFONE_3DIGITS: Final[frozenset[str]] = frozenset(
    {"070", "076", "077", "078", "079", "089", "090", "093"}
)


def is_viettel(phone_number: str) -> bool:
    cleaned = phone_number.strip().replace(" ", "").replace("-", "").replace(".", "")
    if cleaned.startswith("+84"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("84") and len(cleaned) >= 10:
        cleaned = "0" + cleaned[2:]

    return len(cleaned) >= 3 and cleaned[:3] in _VIETTEL_3DIGITS


def is_vinaphone(phone_number: str) -> bool:
    cleaned = phone_number.strip().replace(" ", "").replace("-", "").replace(".", "")
    if cleaned.startswith("+84"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("84") and len(cleaned) >= 10:
        cleaned = "0" + cleaned[2:]

    return len(cleaned) >= 3 and cleaned[:3] in _VINAPHONE_3DIGITS


def is_mobifone(phone_number: str) -> bool:
    cleaned = phone_number.strip().replace(" ", "").replace("-", "").replace(".", "")
    if cleaned.startswith("+84"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("84") and len(cleaned) >= 10:
        cleaned = "0" + cleaned[2:]

    return len(cleaned) >= 3 and cleaned[:3] in _MOBIFONE_3DIGITS


def is_tong_dai(phone_number: str) -> bool:
    """HÀM KIỂM TRA SỐ TỔNG ĐÀI / MÁY BÀN / SỐ KHÔNG PHẢI DI ĐỘNG.

    Loại bỏ:
    - Số Hotline 1900xxxx, 1800xxxx (hoặc 01900..., 01800...)
    - Số máy bàn cố định (02x - ví dụ: 028xx TP.HCM, 024xx Hà Nội)
    - Tất cả các số KHÔNG PHẢI di động cá  10 chữ số chuẩn Việt Nam (03x, 05x, 07x, 08x, 09x).
    """
    cleaned = phone_number.strip().replace(" ", "").replace("-", "").replace(".", "")
    if cleaned.startswith("+84"):
        cleaned = "0" + cleaned[3:]
    elif cleaned.startswith("84") and len(cleaned) >= 10:
        cleaned = "0" + cleaned[2:]

    # 1. Loại bỏ Hotline 1900, 1800, 01900, 01800
    if (
        cleaned.startswith("1900")
        or cleaned.startswith("1800")
        or cleaned.startswith("01900")
        or cleaned.startswith("01800")
    ):
        return True

    # 2. Loại bỏ Số máy bàn cố định (bắt đầu bằng 02x, ví dụ 02839350377)
    if cleaned.startswith("02"):
        return True

    # 3. SIẾT CHẶT: SĐT di động chuẩn Việt Nam BẮT BUỘC phải bắt đầu bằng 03, 05, 07, 08, 09 và đủ đúng 10 chữ số
    if not re.match(r"^0(3|5|7|8|9)\d{8}$", cleaned):
        return True

    return False
