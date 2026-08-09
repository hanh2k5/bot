"""CompanyName value object.

Normalises company name strings (REQ-019).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

from leadhunter.domain.exceptions import InvalidCompanyNameError

_CONTROL_CHARS_PATTERN: Final[re.Pattern[str]] = re.compile(r"[\x00-\x1f\x7f]")


class CompanyName:
    """Immutable value object for a company name.

    Normalisation (REQ-019):
      - Strips leading/trailing whitespace.
      - Removes control characters (U+0000–U+001F, U+007F).
      - Title-cases each word (initial uppercase per word).

    Raises:
        InvalidCompanyNameError: If the name is empty after normalisation.

    Example:
        >>> c = CompanyName("  acme CORP ltd  ")
        >>> c.value
        'Acme Corp Ltd'
    """

    __slots__ = ("_value",)

    def __init__(self, raw: str) -> None:
        if not raw or not isinstance(raw, str):
            raise InvalidCompanyNameError(raw or "")
        # Remove control characters first
        cleaned = _CONTROL_CHARS_PATTERN.sub("", raw)
        # Normalise unicode (NFC) then strip whitespace
        normalised = unicodedata.normalize("NFC", cleaned).strip()
        # Collapse multiple internal spaces and Title-case
        normalised = " ".join(normalised.split()).title()

        if not normalised:
            raise InvalidCompanyNameError(raw)

        self._value: str = normalised

    @property
    def value(self) -> str:
        """Return the normalised company name."""
        return self._value

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"CompanyName('{self._value}')"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CompanyName):
            return self._value.lower() == other._value.lower()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value.lower())
