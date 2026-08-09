"""Excel reader adapter — Infrastructure layer (REQ-006, REQ-001-008).

Reads .xlsx files in streaming/read_only mode to avoid loading the
entire workbook into memory (REQ-006).

Security:
  - File path validated via pathlib before opening.
  - openpyxl opened with read_only=True (no macro execution risk).
  - File size checked at use-case level before reaching this adapter.
  - TODO(security): Future enhancement — validate magic bytes (XLSX = ZIP)
    before processing to detect file type mismatch.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from leadhunter.application.ports.ingestion_source_adapter import (
    IngestionSourceAdapter,
    RawLeadData,
)
from leadhunter.domain.exceptions import FileReadError

logger = logging.getLogger(__name__)


class ExcelReaderAdapter(IngestionSourceAdapter):
    """Streams rows from an .xlsx file using openpyxl read_only mode (REQ-006).

    Args:
        sheet_name: Name of the worksheet to read (default: first sheet).
    """

    def __init__(self, sheet_name: str | None = None) -> None:
        self._sheet_name = sheet_name

    @property
    def source_type(self) -> str:
        """Return source type identifier."""
        return "excel"

    def read(self, source_ref: str) -> Iterator[RawLeadData]:
        """Stream rows from an Excel file.

        Yields rows as RawLeadData, with header normalisation applied.
        The first non-empty row is treated as the header row.

        Args:
            source_ref: Absolute or relative path to the .xlsx file.

        Yields:
            RawLeadData for each data row (1-based row_index, excluding header).

        Raises:
            FileReadError: If the file cannot be opened or parsed.
        """
        # Security: resolve path via pathlib, never trust raw user string in os.path
        file_path = Path(source_ref).resolve()

        try:
            import openpyxl

            wb = openpyxl.load_workbook(
                str(file_path),
                read_only=True,  # REQ-006: streaming mode
                data_only=True,  # Read computed values, not formulas
            )
        except Exception as exc:
            raise FileReadError(str(file_path), exc) from exc

        try:
            sheets_to_read = (
                [wb[self._sheet_name]]
                if self._sheet_name and self._sheet_name in wb.sheetnames
                else wb.worksheets
            )

            data_row_index = 0

            HEADER_ALIASES = {
                "số điện thoại": "phone",
                "sđt": "phone",
                "điện thoại": "phone",
                "phone": "phone",
                "tên cửa hàng": "company_name",
                "tên công ty": "company_name",
                "tên": "company_name",
                "company_name": "company_name",
                "company": "company_name",
                "địa chỉ": "address",
                "address": "address",
                "website": "website",
                "web": "website",
                "email": "email",
                "tên người liên hệ": "contact_name",
                "contact_name": "contact_name",
                "contact": "contact_name",
                "link google maps": "source_reference",
                "tình trạng": "status",
                "status": "status",
                "điểm": "score",
                "score": "score",
                "ghi chú": "notes",
                "notes": "notes",
            }

            for ws in sheets_to_read:
                headers: list[str] = []
                for excel_row in ws.iter_rows(values_only=True):
                    row_values = [str(cell).strip() if cell is not None else "" for cell in excel_row]

                    if not headers:
                        # First row of each sheet is the header
                        raw_headers = [h.lower().strip() for h in row_values]
                        mapped_headers = [HEADER_ALIASES.get(h, h) for h in raw_headers]
                        if any(k in mapped_headers for k in ("phone", "company_name", "address", "website")):
                            headers = mapped_headers
                            logger.debug(
                                f"Excel headers detected in sheet '{ws.title}'",
                                extra={"context": {"headers": headers}},
                            )
                        continue

                    # Skip completely empty rows
                    if not any(row_values):
                        continue

                    data_row_index += 1
                    row_data = {
                        "company_name": "",
                        "contact_name": "",
                        "email": "",
                        "phone": "",
                        "website": "",
                        "address": "",
                        "status": "",
                        "score": "",
                        "notes": "",
                    }
                    for h, val in zip(headers, row_values):
                        if h:
                            row_data[h] = val

                    yield RawLeadData(
                        row_index=data_row_index,
                        data=row_data,
                        source_reference=str(file_path),
                    )
        finally:
            wb.close()
