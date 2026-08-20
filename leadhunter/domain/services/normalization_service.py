"""Domain normalization service.

Pure functions for normalizing raw field values (REQ-017 through REQ-022).
No I/O, no database access, no framework dependencies (REQ-023).
"""

from __future__ import annotations

import re
import unicodedata

from leadhunter.domain.value_objects.company_name import CompanyName
from leadhunter.domain.value_objects.email import Email
from leadhunter.domain.value_objects.phone_number import PhoneNumber
from leadhunter.domain.value_objects.website import Website

_CONTROL_CHARS_PATTERN = re.compile(r"[\x00-\x1f\x7f]")
_EXTRA_WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_email(raw: str) -> Email:
    """Normalize and validate an email address.

    Args:
        raw: Raw email string from external source.

    Returns:
        Validated Email value object.

    Raises:
        InvalidEmailFormatError: If the email is structurally invalid.
    """
    return Email(raw)


def normalize_phone(raw: str) -> PhoneNumber:
    """Normalize a phone number, attempting E.164 format.

    Args:
        raw: Raw phone string from external source.

    Returns:
        PhoneNumber value object (normalized flag indicates E.164 success).
    """
    return PhoneNumber(raw)


def normalize_company_name(raw: str) -> CompanyName:
    """Normalize a company name (strip, title-case, remove control chars).

    Args:
        raw: Raw company name from external source.

    Returns:
        CompanyName value object.

    Raises:
        InvalidCompanyNameError: If empty after normalization.
    """
    return CompanyName(raw)


def normalize_website(raw: str) -> Website:
    """Normalize a website URL (prepend scheme, strip trailing slash, validate).

    Args:
        raw: Raw URL string from external source.

    Returns:
        Website value object.

    Raises:
        InvalidWebsiteError: If the resulting URL is structurally invalid.
    """
    return Website(raw)


def normalize_address(raw: str | None) -> str:
    if not raw:
        return ""
    cleaned = _CONTROL_CHARS_PATTERN.sub("", str(raw))
    cleaned = unicodedata.normalize("NFC", cleaned).strip()
    # Collapse internal multiple spaces/newlines to single space
    cleaned = _EXTRA_WHITESPACE_PATTERN.sub(" ", cleaned)
    return cleaned


def normalize_contact_name(raw: str) -> str:
    """Normalize a contact person's name.

    Strips whitespace and removes control characters. Does not apply
    title-casing to preserve intentional capitalisation (e.g. 'Nguyễn Văn A').

    Args:
        raw: Raw contact name string.

    Returns:
        Normalized contact name string.
    """
    cleaned = _CONTROL_CHARS_PATTERN.sub("", raw)
    return unicodedata.normalize("NFC", cleaned).strip()
