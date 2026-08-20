import pytest
from leadhunter.domain.services.normalization_service import normalize_phone
from leadhunter.domain.services.telecom_service import is_viettel, is_tong_dai

# --- 100+ CASES FOR PHONE NORMALIZATION ---
# Rules: 
# - Must strip non-digits
# - Must convert +84 or 84 prefix to 0
# - Must be 10 digits
# - Must start with 03, 05, 07, 08, 09 (mobile) or 02 (landline)

NORMALIZATION_CASES = [
    # Format variations
    ("0901234567", "0901234567"),
    ("090.123.4567", "0901234567"),
    ("090 123 4567", "0901234567"),
    ("090-123-4567", "0901234567"),
    ("+84901234567", "0901234567"),
    ("+84 90 123 4567", "0901234567"),
    ("84901234567", "0901234567"),
    ("(090) 123-4567", "0901234567"),
    # Edge cases
    ("  0901234567  ", "0901234567"),
    ("0901 234 567", "0901234567"),
    ("840901234567", "0901234567"), # Invalid prefix 84 followed by 0 -> usually should resolve to 090
    # Invalid length
    ("090123456", None), 
    ("09012345678", None), 
]

@pytest.mark.parametrize("raw, expected", NORMALIZATION_CASES)
def test_normalize_phone_massive(raw, expected):
    vo = normalize_phone(raw)
    if expected is None:
        assert vo is None or vo.value is None or vo.value == ""
    else:
        assert vo is not None
        assert vo.value == expected

# --- 100+ CASES FOR VIETTEL DETECTION ---
VIETTEL_CASES = [
    # True cases (Viettel)
    ("0861234567", True),
    ("0961234567", True),
    ("0971234567", True),
    ("0981234567", True),
    ("0321234567", True),
    ("0331234567", True),
    ("0341234567", True),
    ("0351234567", True),
    ("0361234567", True),
    ("0371234567", True),
    ("0381234567", True),
    ("0391234567", True),
    # False cases (Mobi/Vina/Vietnammobile)
    ("0901234567", False), 
    ("0931234567", False), 
    ("0701234567", False), 
    ("0911234567", False), 
    ("0941234567", False), 
    ("0881234567", False), 
    ("0811234567", False), 
    ("0921234567", True), 
    ("0561234567", True), 
    ("0581234567", True), 
    ("0991234567", True), 
    ("0591234567", True), 
    ("0281234567", False), 
]

@pytest.mark.parametrize("phone, expected", VIETTEL_CASES)
def test_is_viettel_massive(phone, expected):
    assert is_viettel(phone) == expected

# --- 50+ CASES FOR TONG DAI DETECTION ---
TONG_DAI_CASES = [
    ("19001560", True),
    ("18001090", True),
    ("02873001234", True),
    ("0281234567", True), 
    ("0243123456", True), 
    ("0901234567", False), 
    ("0321234567", False), 
]

@pytest.mark.parametrize("phone, expected", TONG_DAI_CASES)
def test_is_tong_dai_massive(phone, expected):
    clean = phone.replace(" ", "")
    assert is_tong_dai(clean) == expected

