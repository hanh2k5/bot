"""ExportLeadsToExcelUseCase — Application layer (REQ-056 through REQ-062)."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from leadhunter.application.dtos import ExportParamsDTO, ExportResultDTO
from leadhunter.application.ports.lead_repository import LeadRepository
from leadhunter.domain.constants import EXPORT_FILE_PATTERN
from leadhunter.domain.entities.lead import ExportHistory, LeadStatus
from leadhunter.domain.exceptions import NoDataToExportError

logger = logging.getLogger(__name__)


class ExportLeadsToExcelUseCase:
    """Export leads to an Excel file with configurable filters (REQ-056-062).

    Uses write_only mode and atomic temp-file rename to prevent corrupt output
    (REQ-062). Records export history (REQ-061).

    Args:
        repository: LeadRepository implementation.
        excel_writer: Callable that takes (leads, output_path) and writes Excel.
        export_dir: Default directory for output files.
        actor: Identifier of the user or process.
    """

    def __init__(
        self,
        repository: LeadRepository,
        excel_writer: "ExcelWriterPort",  # type: ignore[name-defined]
        export_dir: str = "exports",
        actor: str = "cli",
    ) -> None:
        self._repository = repository
        self._excel_writer = excel_writer
        self._export_dir = Path(export_dir)
        self._actor = actor

    def execute(self, params: ExportParamsDTO) -> ExportResultDTO:
        """Run the export pipeline.

        Args:
            params: Filter parameters and output path.

        Returns:
            ExportResultDTO with output_file_path and record_count.

        Raises:
            NoDataToExportError: If no records match the filters (REQ-060).
        """
        start_time = time.monotonic()
        logger.info(
            "ExportLeadsToExcelUseCase started",
            extra={"context": {"actor": params.actor, "filters": vars(params)}},
        )

        status_enum: Optional[LeadStatus] = None
        if params.status:
            try:
                status_enum = LeadStatus(params.status.upper())
            except ValueError:
                pass

        leads = self._repository.list_all_for_export(
            status=status_enum,
            score_min=params.score_min,
            score_max=params.score_max,
            source=params.source,
            keyword=params.keyword,
            created_from=params.created_from,
            created_to=params.created_to,
        )

        # Slice to the latest 80 leads so export only contains 80 newest records
        if len(leads) > 80:
            leads = leads[-80:]

        if not leads:
            raise NoDataToExportError("the specified filters")

        # Determine output path: nguon 1.xlsx, nguon 2.xlsx, nguon 3.xlsx...
        if params.output_path:
            out_path = Path(params.output_path)
            if not out_path.suffix:
                out_path = out_path.with_suffix(".xlsx")
        else:
            self._export_dir.mkdir(parents=True, exist_ok=True)
            i = 1
            while (self._export_dir / f"nguon {i}.xlsx").exists():
                i += 1
            out_path = self._export_dir / f"nguon {i}.xlsx"

        # Write Excel using the adapter (.xlsx)
        self._excel_writer.write(leads, str(out_path))

        record_count = len(leads)
        executed_at = datetime.now(timezone.utc).isoformat()

        # REQ-061: Record export history
        filter_criteria = json.dumps(
            {k: v for k, v in vars(params).items() if v is not None}
        )
        history = ExportHistory(
            filter_criteria=filter_criteria,
            record_count=record_count,
            output_file_path=str(out_path.resolve()),
            actor=params.actor,
        )
        self._repository.add_export_history(history)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "ExportLeadsToExcelUseCase completed",
            extra={
                "context": {
                    "record_count": record_count,
                    "output_file_path": str(out_path),
                    "elapsed_ms": round(elapsed_ms, 2),
                }
            },
        )

        return ExportResultDTO(
            output_file_path=str(out_path.resolve()),
            record_count=record_count,
            executed_at=executed_at,
        )


class ExcelWriterPort:
    """Protocol / stub for the Excel writer adapter.

    The actual implementation resides in the Infrastructure layer.
    This stub satisfies type checkers within the application layer.
    """

    def write(self, leads: list, output_path: str) -> None:
        """Write leads to an Excel file.

        Args:
            leads: List of Lead entities to write.
            output_path: Target file path (must end in .xlsx).
        """
        raise NotImplementedError
