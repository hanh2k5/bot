"""Email value object.

Provides an immutable, validated email address representation (REQ-017).
Validation follows RFC 5322 simplified: local-part@domain.
Invalid emails raise InvalidEmailFormatError at construction time (REQ-021).
"""

from __future__ import annotations

import re
from typing import Final

from leadhunter.domain.exceptions import InvalidEmailFormatError

# Simplified RFC 5322 pattern — covers the vast majority of real-world emails.
# Does NOT support quoted local-parts or IP-literal domains (acceptable for B2B data).
_EMAIL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


class Email:
    """Immutable value object representing a validated, normalised email address.

    Normalisation (REQ-017):
      - Strips leading/trailing whitespace.
      - Converts to lowercase.
      - Validates against RFC 5322 simplified pattern.

    Raises:
        InvalidEmailFormatError: If the input does not match the email pattern.

    Example:
        >>> email = Email("  User@Example.COM  ")
        >>> str(email)
        'user@example.com'
    """

    __slots__ = ("_value",)

    def __init__(self, raw: str) -> None:
        """Construct and validate an Email value object.

        Args:
            raw: Raw email string from an external source (file, web, etc.).

        Raises:
            InvalidEmailFormatError: If ``raw`` is not a valid email format.
        """
        normalised = raw.strip().lower()
        if not _EMAIL_PATTERN.match(normalised):
            raise InvalidEmailFormatError(raw)
        self._value: str = normalised

    @property
    def value(self) -> str:
        """Return the normalised email string."""
        return self._value

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"Email('{self._value}')"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Email):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)
