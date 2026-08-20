import re

JUNK_NAMES = {
    "ho chi minh", "vietnam", "viet nam", "district",
    "ho chi minh city", "binh thanh", "tan binh",
    "see nearby", "see similar places", "similar places", "nearby cafes", "directions", "overview", "reviews",
    "english", "vietnamese",
    "tạp hóa", "cầm đồ", "mầm non", "bách hóa", "tap hoa", "cam do", "mam non", "bach hoa"
}

_DISTRICT_RE = re.compile(
    r"^(qu[aậ]n|qu[áa]n|ph[uư][oờ]ng|huy[eệ]n|t[hH][uị])\s*\d*$",
    re.IGNORECASE
)

UI_JUNK = {
    "restroom", "gender-neutral restroom", "paid street parking", "street parking",
    "parking", "education center", "training center", "sunday", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "photo", "recycling", "payments",
    "claim this business", "debit cards", "open 24 hours", "full restoration service",
    "checks", "accessible entrance", "wheelchair"
}

def is_place_id_or_junk(nm: str) -> bool:
    nm = nm.strip()
    if not nm or len(nm) < 2:
        return True
    if "|" in nm or nm.startswith("0a") or nm.startswith("ChI") or nm.startswith("0x") or nm.startswith("CIH"):
        return True
    if " " not in nm and len(nm) >= 7:
        has_upper = any(c.isupper() for c in nm)
        has_lower = any(c.islower() for c in nm)
        has_digit = any(c.isdigit() or c in "-_" for c in nm)
        if (has_upper and has_lower) or has_digit:
            return True
    nm_l = nm.lower()
    if any(u in nm_l for u in UI_JUNK):
        return True
    return False

def extract_name(snippet: str) -> str:
    name_m = re.findall(
        r'"([A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ][^"]{3,50})"',
        snippet
    )
    for nm in name_m:
        nm = nm.strip()
        if is_place_id_or_junk(nm):
            continue
        if any(j in nm.lower() for j in JUNK_NAMES):
            continue
        if _DISTRICT_RE.match(nm):
            continue
        if len(nm) > 4:
            return nm
    return ""

def extract_address(snippet: str) -> str:
    addr_m = re.findall(
        r'"(\d+[^"]{5,150}(?:Hồ Chí Minh|Ho Chi Minh|HCM|Vietnam|Việt Nam)[^"]{0,30})"',
        snippet
    )
    # 2. Bắt chuỗi địa chỉ tổng quát có chứa HCM / Vietnam
    addr_m2 = re.findall(
        r'"([^"]{8,150}(?:Hồ Chí Minh|Ho Chi Minh|HCM|Vietnam|Việt Nam)[^"]{0,30})"',
        snippet
    )
    for a in addr_m:
        a_clean = a.strip()
        if not a_clean.startswith("0") and len(a_clean) > 15:
            return a_clean
    return ""

def is_clean_phone(p_str: str) -> tuple[bool, str]:
    if not p_str: return False, ""
    c = p_str.replace(" ", "").replace(".", "").replace("-", "").replace("+84", "0")
    if c.startswith("840"):
        c = "0" + c[3:]
    elif c.startswith("84"):
        c = "0" + c[2:]
    if len(c) != 10: return False, c
    if c.startswith("02"): return False, c
    if not c.startswith(("03", "05", "07", "08", "09")): return False, c
    return True, c

def is_professional_website(url: str) -> bool:
    if not url: return False
    url = url.lower()
    if "facebook.com" in url or "zalo.me" in url or "instagram.com" in url or "tiktok.com" in url:
        return False
    if "shopee.vn" in url or "lazada.vn" in url or "tiki.vn" in url or "foody.vn" in url or "shopeefood.vn" in url or "grab.com" in url:
        return False
    if "google.com" in url or "business.site" in url or "site.com" in url:
        return False
    return True

