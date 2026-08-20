"""Domain deduplication service.

Provides the business-logic key computation for duplicate detection (REQ-024).
Pure functions — no I/O, no DB (REQ-023).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeduplicationConfig:
    """Configuration for which dedup rules are active (REQ-024).

    Attributes:
        use_email_dedup: If True, identical normalised emails are duplicates.
        use_company_phone_dedup: If True, identical (company_name, phone)
            pairs (after normalization, case-insensitive) are duplicates.
    """

    use_email_dedup: bool = True
    use_company_phone_dedup: bool = True


def compute_email_dedup_key(email: str) -> str:
    """Return the normalised dedup key for email-based deduplication.

    Args:
        email: Already-normalised email string (lowercase, stripped).

    Returns:
        Lowercase email string used as a dedup key.
    """
    return email.strip().lower()


def compute_company_phone_dedup_key(company_name: str, phone: str) -> tuple[str, str]:
    """Return the normalised key pair for company+phone deduplication.

    Args:
        company_name: Already-normalised company name.
        phone: Already-normalised phone string.

    Returns:
        A tuple of (lowercase_company_name, digits_only_phone).
    """
    normalized_company = company_name.strip().lower()
    # Strip all non-digit chars for phone comparison
    digits_only = "".join(ch for ch in phone if ch.isdigit())
    return normalized_company, digits_only
