import pytest
from leadhunter.infrastructure.adapters.maps_utils import is_place_id_or_junk, extract_name, extract_address, is_clean_phone, is_professional_website

JUNK_TESTS = [
    ("Tạp Hóa Chị Nở", True), # Should be junk! wait, extract_name filters JUNK_NAMES. is_place_id_or_junk doesn't filter JUNK_NAMES. So we need to test extract_name with mock snippet instead!
]

def test_extract_name():
    # snippet format: `"Name"`
    snippet = 'some junk "Tạp Hóa Cô 3" more junk "Cửa Hàng Sửa Xe" and "0901234567"'
    name = extract_name(snippet)
    # Tạp Hóa is junk, so it should be skipped and return Cửa Hàng Sửa Xe
    assert name == "Cửa Hàng Sửa Xe"
    
    snippet2 = '"Cầm Đồ Tý" "Trường Mầm Non Họa Mi" "Nhà Hàng Biển Xanh"'
    assert extract_name(snippet2) == "Nhà Hàng Biển Xanh"

def test_extract_address():
    snippet = '"123 Đường Cộng Hòa, Tân Bình, Hồ Chí Minh" and junk'
    assert extract_address(snippet) == "123 Đường Cộng Hòa, Tân Bình, Hồ Chí Minh"

def test_is_professional_website():
    assert is_professional_website("https://facebook.com/fanpage") == False
    assert is_professional_website("https://shopee.vn/shop") == False
    assert is_professional_website("https://thienlong.vn") == True
    assert is_professional_website("https://example.business.site") == False

