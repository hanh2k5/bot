"""Excel writer adapter — Infrastructure layer (REQ-057, REQ-058, REQ-062).

Writes leads to .xlsx using openpyxl write_only mode for memory efficiency.
Uses atomic temp-file write + rename to prevent corrupt output (REQ-062).

Security:
  - Output path validated via pathlib, not user-controlled raw strings.
  - TODO(security): Validate output directory is within allowed sandbox path.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from leadhunter.domain.entities.lead import Lead

from leadhunter.domain.constants import EXPORT_COLUMNS
from leadhunter.domain.exceptions import FileWriteError

logger = logging.getLogger(__name__)


class ExcelWriterAdapter:
    """Writes lead records to an .xlsx file (REQ-057-062).

    Uses openpyxl write_only=True for memory efficiency (REQ-058).
    Writes to a .tmp file first, then renames atomically (REQ-062).
    """

    def write(self, leads: list["Lead"], output_path: str) -> None:
        """Write leads to an Excel file matching user requested format and styling."""
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        out_path = Path(output_path)
        tmp_path = out_path.with_suffix(".tmp")

        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Leads"

            # Column headers: SĐT | Tên Cửa Hàng | Địa chỉ | Link Google Maps | Tình trạng
            headers = ["Số Điện Thoại", "Tên Cửa Hàng", "Địa Chỉ", "Link Google Maps", "Tình Trạng"]
            ws.append(headers)

            # Styling definitions
            header_fill = PatternFill(start_color="1B5583", end_color="1B5583", fill_type="solid")
            header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            header_align = Alignment(horizontal="left", vertical="center")

            thin_border = Border(
                left=Side(style="thin", color="D9D9D9"),
                right=Side(style="thin", color="D9D9D9"),
                top=Side(style="thin", color="D9D9D9"),
                bottom=Side(style="thin", color="D9D9D9"),
            )

            # Apply header styling
            for col_idx, cell in enumerate(ws[1], 1):
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = header_align

            # Data rows
            for lead in leads:
                phone_str = lead.phone or ""
                # Keep original phone format or 0...
                if phone_str.startswith("+84"):
                    phone_str = "0" + phone_str[3:]

                link_src = lead.source_reference or ""
                status_str = ""  # Tình trạng để trống theo yêu cầu

                row = [
                    phone_str,
                    lead.company_name or "",
                    lead.address or "",
                    link_src,
                    status_str
                ]
                ws.append(row)

          # Căn chỉnh tỷ lệ cột y hệt mẫu mới (Link nhỏ lại, Tên/Địa chỉ/Tình trạng rộng ra)
            col_widths = {"A": 15, "B": 45, "C": 75, "D": 18, "E": 50}
            for col_letter, width in col_widths.items():
                ws.column_dimensions[col_letter].width = width

            # Bảng màu chuẩn theo mẫu hình image_380303.png
            fill_colors = {
                1: PatternFill(start_color="C6E0B4", end_color="C6E0B4", fill_type="solid"), # Cột 1 (SĐT): Xanh lá nhạt
                2: PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid"), # Cột 2 (Tên): Vàng nhạt
                3: PatternFill(start_color="C9DAF8", end_color="C9DAF8", fill_type="solid"), # Cột 3 (Địa chỉ): Xanh dương nhạt
                4: PatternFill(start_color="F4CCCC", end_color="F4CCCC", fill_type="solid"), # Cột 4 (Link): Đỏ/Hồng nhạt
                5: PatternFill(start_color="D9D2E9", end_color="D9D2E9", fill_type="solid")  # Cột 5 (Tình trạng): Tím nhạt
            }

            for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=5):
                for cell in row:
                    cell.border = thin_border
                    cell.alignment = Alignment(horizontal="left", vertical="center")
                    # Tự động đổ màu theo số thứ tự của cột
                    if cell.column in fill_colors:
                        cell.fill = fill_colors[cell.column]

            # Apply AutoFilter to the header row
            ws.auto_filter.ref = f"A1:E{ws.max_row}"
            
            # Freeze the top row
            ws.freeze_panes = "A2"

            # Write to temp file first (atomic write)
            wb.save(str(tmp_path))

            # Atomic rename
            os.replace(str(tmp_path), str(out_path))

            logger.info(
                "Excel file written successfully",
                extra={
                    "context": {
                        "output_path": str(out_path),
                        "record_count": len(leads),
                    }
                },
            )

        except Exception as exc:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise FileWriteError(str(out_path), exc) from exc
