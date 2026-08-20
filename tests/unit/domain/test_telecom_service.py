"""Unit tests for telecom_service.py."""

from leadhunter.domain.services.telecom_service import is_viettel


def test_is_viettel_local() -> None:
    # Viettel local numbers
    assert is_viettel("0981234567") is True
    assert is_viettel("0359876543") is True
    assert is_viettel("0861112222") is True


def test_is_viettel_e164() -> None:
    # Viettel E.164 numbers
    assert is_viettel("+84981234567") is True
    assert is_viettel("84359876543") is True


def test_is_not_viettel() -> None:
    # Other networks (Mobi: 090, Vina: 091)
    assert is_viettel("0901234567") is False
    assert is_viettel("0919876543") is False
    assert is_viettel("0905555555") is False
    assert is_viettel("+84901234567") is False
    assert is_viettel("84919876543") is False


def test_is_viettel_empty_or_invalid() -> None:
    assert is_viettel("") is False
    assert is_viettel("12345") is False
