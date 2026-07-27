"""Unit tests for normalization service (REQ-017 through REQ-022)."""

import pytest

from leadhunter.domain.exceptions import (
    InvalidCompanyNameError,
    InvalidEmailFormatError,
    InvalidWebsiteError,
)
from leadhunter.domain.services.normalization_service import (
    normalize_address,
    normalize_company_name,
    normalize_contact_name,
    normalize_email,
    normalize_phone,
    normalize_website,
)


class TestNormalizeEmail:
    def test_lowercases_and_strips(self) -> None:
        result = normalize_email("  USER@EXAMPLE.COM  ")
        assert result.value == "user@example.com"

    def test_invalid_raises(self) -> None:
        with pytest.raises(InvalidEmailFormatError):
            normalize_email("not-an-email")


class TestNormalizePhone:
    def test_e164_phone_normalized(self) -> None:
        result = normalize_phone("+84912345678")
        assert result.normalized is True
        assert result.value == "+84912345678"

    def test_non_e164_not_normalized(self) -> None:
        result = normalize_phone("0912345678")
        assert result.normalized is False

    def test_strips_non_digits(self) -> None:
        result = normalize_phone("+84 (091) 234-5678")
        assert "+" in result.value


class TestNormalizeCompanyName:
    def test_title_case(self) -> None:
        result = normalize_company_name("acme corporation ltd")
        assert result.value == "Acme Corporation Ltd"

    def test_strips_control_chars(self) -> None:
        result = normalize_company_name("Corp\x00Name")
        assert "\x00" not in result.value

    def test_empty_after_strip_raises(self) -> None:
        with pytest.raises(InvalidCompanyNameError):
            normalize_company_name("   ")


class TestNormalizeWebsite:
    def test_prepends_https(self) -> None:
        result = normalize_website("example.com")
        assert result.value.startswith("https://")

    def test_strips_trailing_slash(self) -> None:
        result = normalize_website("https://example.com/")
        assert not result.value.endswith("/")

    def test_invalid_url_raises(self) -> None:
        with pytest.raises(InvalidWebsiteError):
            normalize_website("not a url")


class TestNormalizeAddress:
    def test_strips_whitespace(self) -> None:
        result = normalize_address("  123 Main St  ")
        assert result == "123 Main St"

    def test_collapses_internal_spaces(self) -> None:
        result = normalize_address("123  Main   St")
        assert result == "123 Main St"

    def test_removes_control_chars(self) -> None:
        result = normalize_address("123 Main\x00 St")
        assert "\x00" not in result


class TestNormalizeContactName:
    def test_strips_whitespace(self) -> None:
        result = normalize_contact_name("  Nguyen Van A  ")
        assert result == "Nguyen Van A"

    def test_removes_control_chars(self) -> None:
        result = normalize_contact_name("Name\x01Here")
        assert "\x01" not in result
