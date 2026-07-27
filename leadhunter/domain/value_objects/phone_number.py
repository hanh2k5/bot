"""PhoneNumber value object.

Provides normalisation and validation for telephone numbers (REQ-018).
"""

from __future__ import annotations

import re
from typing import Final

# Strip all chars except digits
_DIGITS_ONLY_PATTERN: Final[re.Pattern[str]] = re.compile(r"[^\d]")
# E.164: starts with + followed by 7-15 digits
_E164_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\+\d{7,15}$")


class PhoneNumber:
    """Immutable value object for a telephone number.

    Normalisation (REQ-018):
      - If the raw string already includes a '+' prefix (E.164 candidate),
        strip all non-digit/non-plus chars and validate E.164 format.
      - Otherwise, strip all non-digit chars, keep the result as-is,
        and mark ``normalized = False``.

    Attributes:
        value: The normalised phone string.
        normalized: True if successfully normalised to E.164 format.

    Example:
        >>> p = PhoneNumber("+84 (0)91-234-5678")
        >>> p.value
        '+84091234 5678'  # non-digit stripped
        >>> p.normalized
        True (if valid E.164)
    """

    __slots__ = ("_value", "_normalized")

    def __init__(self, raw: str) -> None:
        """Construct and normalise a PhoneNumber.

        Args:
            raw: Raw phone string from an external source.
        """
        stripped = raw.strip()
        # Remove all non-digit characters
        digits_only = _DIGITS_ONLY_PATTERN.sub("", stripped)
        # Reconstruct with leading '+' if the original had one
        if stripped.startswith("+"):
            candidate = "+" + digits_only
        else:
            candidate = digits_only

        if _E164_PATTERN.match(candidate):
            self._value: str = candidate
            self._normalized: bool = True
        else:
            # Keep partially cleaned form but flag as non-normalised
            self._value = candidate if candidate else digits_only
            self._normalized = False

    @property
    def value(self) -> str:
        """Return the normalised/stripped phone string."""
        return self._value

    @property
    def normalized(self) -> bool:
        """True if the number was successfully normalised to E.164 format."""
        return self._normalized

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        flag = "E.164" if self._normalized else "raw"
        return f"PhoneNumber('{self._value}', {flag})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PhoneNumber):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)
