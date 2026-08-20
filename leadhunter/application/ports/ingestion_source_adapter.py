"""IngestionSourceAdapter port — Application layer.

Defines the abstract interface that all data ingestion adapters must implement
(ARCH-008). This pattern allows Phase 2 API adapters to be added without
modifying existing use cases (Open/Closed Principle).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator


class RawLeadData:
    """Simple container for one row of raw lead data from any ingestion source.

    Attributes:
        row_index: 1-based row number in the source (for error reporting).
        data: Dictionary mapping column names to raw string values.
        source_reference: The original file path or URL.
    """

    __slots__ = ("row_index", "data", "source_reference")

    def __init__(
        self,
        row_index: int,
        data: dict[str, str],
        source_reference: str,
    ) -> None:
        """Initialise raw lead data.

        Args:
            row_index: 1-based position in the source.
            data: Raw field name → raw string value mapping.
            source_reference: File path or URL from which data was read.
        """
        self.row_index = row_index
        self.data = data
        self.source_reference = source_reference


class IngestionSourceAdapter(ABC):
    """Abstract adapter for reading raw lead data from any source (ARCH-008).

    Implementations must live in the Infrastructure layer (Excel, CSV, Web).
    """

    @abstractmethod
    def read(self, source_ref: str) -> Iterator[RawLeadData]:
        """Read raw lead records from the given source reference.

        The method MUST yield data row-by-row (streaming), never loading
        all records into memory at once (REQ-006).

        Args:
            source_ref: File path, URL, or other identifier for the source.

        Yields:
            RawLeadData for each row/record in the source.

        Raises:
            InfrastructureError: On I/O or network failure.
            FileTooLargeError: If the source exceeds configured size limits.
        """
        ...

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return a short identifier for this source type (e.g. 'excel', 'web').

        Returns:
            Lowercase source type string.
        """
        ...
