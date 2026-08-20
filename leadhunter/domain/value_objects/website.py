"""Website value object.

Normalises and validates website URLs (REQ-020).
"""

from __future__ import annotations

import re
from typing import Final
from urllib.parse import urlparse

from leadhunter.domain.exceptions import InvalidWebsiteError

_VALID_SCHEMES: Final[frozenset[str]] = frozenset({"http", "https"})


class Website:
    """Immutable value object for a website URL.

    Normalisation (REQ-020):
      - If the raw string lacks a scheme, prepend ``https://``.
      - Strip trailing slashes from the path (unless it's the root ``/``).
      - Validate that the result has a valid scheme (http/https) and a non-empty
        netloc (domain).

    Raises:
        InvalidWebsiteError: If the URL is structurally invalid after normalisation.

    Example:
        >>> w = Website("example.com/")
        >>> w.value
        'https://example.com'
    """

    __slots__ = ("_value",)

    # Allow optional path after domain, reject bare strings without dots
    _DOMAIN_PATTERN: Final[re.Pattern[str]] = re.compile(
        r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z]{2,})+$"
    )

    def __init__(self, raw: str) -> None:
        """Construct and normalise a Website.

        Args:
            raw: Raw URL string from an external source.

        Raises:
            InvalidWebsiteError: If the resulting URL is not a valid http/https URL.
        """
        stripped = raw.strip()
        if not stripped:
            raise InvalidWebsiteError(raw)

        # Prepend https:// if no scheme present
        if not re.match(r"^https?://", stripped, re.IGNORECASE):
            stripped = "https://" + stripped

        # Strip trailing slashes from path component
        # e.g. https://example.com/// → https://example.com
        candidate = re.sub(r"/+$", "", stripped)

        parsed = urlparse(candidate)
        netloc = parsed.netloc
        # Security/correctness: netloc must be non-empty, contain a dot,
        # and have no whitespace (rejects "https://not a url")
        if (
            parsed.scheme.lower() not in _VALID_SCHEMES
            or not netloc
            or "." not in netloc
            or " " in netloc
        ):
            raise InvalidWebsiteError(raw)

        self._value: str = candidate

    @property
    def value(self) -> str:
        """Return the normalised website URL."""
        return self._value

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"Website('{self._value}')"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Website):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)
