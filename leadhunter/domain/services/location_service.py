"""Location Domain Service — Golden Triangle Geographic Scope Filtering."""

from __future__ import annotations

import re
from typing import Final

_GOLDEN_TRIANGLE_TOKENS: Final[list[str]] = [
    "hồ chí minh", "ho chi minh", "hcm", "tphcm", "tp hcm", "sài gòn", "sai gon",
    "bình dương", "binh duong", "thủ dầu một", "thu dau mot", "dĩ an", "di an",
    "thuận an", "thuan an", "bến cát", "ben cat", "tân uyên", "tan uyen", "bàu bàng", "bau bang",
    "đồng nai", "dong nai", "biên hòa", "bien hoa", "long thành", "long thanh",
    "nhơn trạch", "nhon trach", "trảng bom", "trang bom", "long khánh", "long khanh", "cẩm mỹ", "cam my",
    "quận 1", "quận 2", "quận 3", "quận 4", "quận 5", "quận 6", "quận 7", "quận 8", "quận 9", "quận 10", "quận 11", "quận 12",
    "quan 1", "quan 2", "quan 3", "quan 4", "quan 5", "quan 6", "quan 7", "quan 8", "quan 9", "quan 10", "quan 11", "quan 12",
    "bình thạnh", "binh thanh", "tân bình", "tan binh", "phú nhuận", "phu nhuan", "gò vấp", "go vap",
    "tân phú", "tan phu", "bình tân", "binh tan", "thủ đức", "thu duc", "hóc môn", "hoc mon",
    "củ chi", "cu chi", "nhà bè", "nha be", "bình chánh", "binh chanh"
]

_OTHER_PROVINCES: Final[list[str]] = [
    "hà nội", "ha noi", "cần thơ", "can tho", "long an", "tân an", "tan an",
    "tiền giang", "tien giang", "mỹ tho", "my tho", "bến tre", "ben tre",
    "vĩnh long", "vinh long", "đồng tháp", "dong thap", "đà nẵng", "da nang",
    "hải phòng", "hai phong", "nha trang", "vũng tàu", "vung tau"
]


def is_in_golden_triangle(address: str) -> bool:
    """Check if address strictly belongs to Golden Triangle (TP.HCM, Bình Dương, Đồng Nai)."""
    if not address or not isinstance(address, str):
        return False

    addr_trim = address.strip()
    if len(addr_trim) < 3:
        return False

    if re.match(r"^[A-Z0-9]{2,4}\+[A-Z0-9]{2,3}", addr_trim):
        return False

    a = addr_trim.lower()
    a_clean = re.sub(
        r"[^\w\sàáảãạăắcằẳẵặâấầnẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]",
        " ",
        a,
    )
    words_set = set(a_clean.split())

    has_valid_token = False
    for token in _GOLDEN_TRIANGLE_TOKENS:
        if token in a or token in a_clean or token in words_set:
            has_valid_token = True
            break

    if not has_valid_token:
        return False

    for other in _OTHER_PROVINCES:
        if other in a:
            return False

    return True
