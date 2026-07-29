"""PhoneNumber value object.

Provides normalisation and validation for telephone numbers (REQ-018).
"""

from __future__ import annotations
import re
from typing import Final

_DIGITS_ONLY_PATTERN: Final[re.Pattern[str]] = re.compile(r"[^\d]")

class PhoneNumber:
    __slots__ = ("_value", "_normalized")

    def __init__(self, raw: str) -> None:
        stripped = raw.strip()
        
        # Replace +84 or 84 at start with 0
        if stripped.startswith("+84"):
            stripped = "0" + stripped[3:]
        
        digits_only = _DIGITS_ONLY_PATTERN.sub("", stripped)
        
        if digits_only.startswith("840"):
            digits_only = "0" + digits_only[3:]
        elif digits_only.startswith("84"):
            digits_only = "0" + digits_only[2:]
            
        if len(digits_only) == 10 and digits_only.startswith(("03", "05", "07", "08", "09", "02")):
            self._value = digits_only
            self._normalized = True
        else:
            self._value = None
            self._normalized = False

    @property
    def value(self) -> str | None:
        return self._value

    @property
    def normalized(self) -> bool:
        return self._normalized

    def __str__(self) -> str:
        return self._value if self._value else ""

    def __repr__(self) -> str:
        return f"PhoneNumber('{self._value}', {self._normalized})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PhoneNumber):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)
