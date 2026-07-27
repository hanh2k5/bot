"""CSV reader adapter — Infrastructure layer (REQ-004).

Reads .csv files with UTF-8 and UTF-8-BOM encoding support.

Security:
  - File path validated via pathlib before opening.
  - No shell commands or subprocesses — pure Python csv module.
  - TODO(security): Validate file magic bytes to ensure it's a text/CSV file.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Iterator

from leadhunter.application.ports.ingestion_source_adapter import (
    IngestionSourceAdapter,
    RawLeadData,
)
from leadhunter.domain.constants import SUPPORTED_CSV_ENCODINGS
from leadhunter.domain.exceptions import FileReadError, UnsupportedEncodingError

logger = logging.getLogger(__name__)


class CsvReaderAdapter(IngestionSourceAdapter):
    """Streams rows from a .csv file (REQ-004).

    Supports UTF-8 and UTF-8-BOM encodings (REQ-004).

    Args:
        delimiter: CSV field delimiter (default ',').
    """

    def __init__(self, delimiter: str = ",") -> None:
        self._delimiter = delimiter

    @property
    def source_type(self) -> str:
        """Return source type identifier."""
        return "csv"

    def read(self, source_ref: str) -> Iterator[RawLeadData]:
        """Stream rows from a CSV file.

        Tries encodings in order: utf-8-sig (BOM), utf-8. Raises
        UnsupportedEncodingError if neither works (REQ-004).

        Args:
            source_ref: Path to the .csv file.

        Yields:
            RawLeadData for each data row (skipping header).

        Raises:
            UnsupportedEncodingError: If the file encoding is not supported.
            FileReadError: If the file cannot be read.
        """
        file_path = Path(source_ref).resolve()
        encoding_used: str | None = None

        for encoding in SUPPORTED_CSV_ENCODINGS:
            try:
                # Probe the file with the candidate encoding
                with open(str(file_path), encoding=encoding, errors="strict") as f:
                    f.read(1024)  # Read a chunk to detect encoding issues
                encoding_used = encoding
                break
            except UnicodeDecodeError:
                continue
            except OSError as exc:
                raise FileReadError(str(file_path), exc) from exc

        if encoding_used is None:
            raise UnsupportedEncodingError(str(file_path))

        try:
            with open(str(file_path), encoding=encoding_used, newline="") as f:
                reader = csv.DictReader(f, delimiter=self._delimiter)
                for row_index, row in enumerate(reader, start=1):
                    if not any(row.values()):
                        continue  # Skip blank rows
                    yield RawLeadData(
                        row_index=row_index,
                        data={k.strip().lower(): v.strip() for k, v in row.items() if k},
                        source_reference=str(file_path),
                    )
        except UnicodeDecodeError as exc:
            raise UnsupportedEncodingError(str(file_path)) from exc
        except OSError as exc:
            raise FileReadError(str(file_path), exc) from exc
