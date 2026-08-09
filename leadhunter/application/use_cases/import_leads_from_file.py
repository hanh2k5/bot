"""ImportLeadsFromFileUseCase — Application layer.

Handles REQ-001 through REQ-008: importing leads from Excel or CSV files.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from leadhunter.application.dtos import (
    ImportResultDTO,
    ImportRowErrorDTO,
)
from leadhunter.application.ports.ingestion_source_adapter import (
    IngestionSourceAdapter,
)
from leadhunter.application.ports.lead_repository import LeadRepository
from leadhunter.domain.constants import (
    DEFAULT_LEAD_STATUS,
    REQUIRED_IMPORT_COLUMNS,
)
from leadhunter.domain.entities.lead import ImportHistory, Lead, LeadStatus
from leadhunter.domain.exceptions import (
    DomainError,
    DuplicateLeadError,
    FileTooLargeError,
    MissingRequiredColumnError,
)
from leadhunter.domain.services.dedup_service import (
    DeduplicationConfig,
    compute_company_phone_dedup_key,
    compute_email_dedup_key,
)
from leadhunter.domain.services.normalization_service import (
    normalize_address,
    normalize_company_name,
    normalize_contact_name,
    normalize_email,
    normalize_phone,
    normalize_website,
)

logger = logging.getLogger(__name__)

# Allowed sort fields (REQ-045) — used for validation
_MAX_FILE_SIZE_DEFAULT_MB: float = 50.0


class ImportLeadsFromFileUseCase:
    """Import leads from an Excel (.xlsx) or CSV file (REQ-001 through REQ-008).

    This use case:
      - Validates file size before reading (REQ-005).
      - Validates required columns exist (REQ-002).
      - Streams rows to avoid loading the entire file into memory (REQ-006).
      - Normalises each field via the Domain layer (REQ-017-022).
      - Performs duplicate detection and logs duplicates (REQ-024, REQ-025).
      - Generates a unique import_batch_id (REQ-007).
      - Records an ImportHistory entry (REQ-008).
      - Logs start/end lines with timing (NFR-013).

    Args:
        repository: The LeadRepository implementation to persist records.
        adapter: The IngestionSourceAdapter implementation (Excel or CSV).
        dedup_config: Configuration for which dedup rules are active.
        max_file_size_mb: Maximum allowed file size in megabytes.
        actor: Identifier of the user or process running this use case.
    """

    def __init__(
        self,
        repository: LeadRepository,
        adapter: IngestionSourceAdapter,
        dedup_config: Optional[DeduplicationConfig] = None,
        max_file_size_mb: float = _MAX_FILE_SIZE_DEFAULT_MB,
        actor: str = "cli",
    ) -> None:
        self._repository = repository
        self._adapter = adapter
        self._dedup_config = dedup_config or DeduplicationConfig()
        self._max_file_size_mb = max_file_size_mb
        self._actor = actor

    def execute(self, file_path: str) -> ImportResultDTO:
        """Run the import pipeline for the given file.

        Args:
            file_path: Absolute or relative path to the .xlsx file.

        Returns:
            ImportResultDTO with success_count, error_count, duplicate_count,
            and per-row error details.

        Raises:
            FileTooLargeError: If file exceeds max_file_size_mb (REQ-005).
            MissingRequiredColumnError: If a required column is absent (REQ-002).
        """
        batch_id = str(uuid.uuid4())
        start_time = time.monotonic()
        path = Path(file_path)

        logger.info(
            "ImportLeadsFromFileUseCase started",
            extra={
                "context": {
                    "import_batch_id": batch_id,
                    "file_path": str(path.name),
                    "actor": self._actor,
                }
            },
        )

        # REQ-005: Check file size before reading
        if path.exists():
            actual_mb = path.stat().st_size / (1024 * 1024)
            if actual_mb > self._max_file_size_mb:
                raise FileTooLargeError(str(path), self._max_file_size_mb, actual_mb)

        success_count = 0
        error_count = 0
        duplicate_count = 0
        row_errors: list[ImportRowErrorDTO] = []

        try:
            row_iterator = self._adapter.read(file_path)
            headers_validated = False

            for raw_row in row_iterator:
                # REQ-002: Validate required columns on first row
                if not headers_validated:
                    self._validate_columns(raw_row.data, batch_id)
                    headers_validated = True

                # REQ-003: Per-row validation — skip invalid rows, continue processing
                try:
                    lead = self._build_lead(raw_row.data, batch_id, file_path)
                except DomainError as exc:
                    error_count += 1
                    row_errors.append(
                        ImportRowErrorDTO(
                            row_index=raw_row.row_index,
                            field=_infer_field_from_error(exc),
                            error_code=exc.error_code,
                            message=exc.message,
                        )
                    )
                    logger.debug(
                        "Row skipped due to domain validation error",
                        extra={
                            "context": {
                                "row_index": raw_row.row_index,
                                "error_code": exc.error_code,
                            }
                        },
                    )
                    continue

                # REQ-024/025: Dedup check
                dup_lead_id = self._find_duplicate(lead)
                if dup_lead_id is not None:
                    duplicate_count += 1
                    from leadhunter.domain.entities.lead import DuplicateLog

                    dup_log = DuplicateLog(
                        original_lead_id=dup_lead_id,
                        duplicate_data=json.dumps(raw_row.data),
                        import_batch_id=batch_id,
                    )
                    self._repository.add_duplicate_log(dup_log)
                    
                    # Update existing record's notes and status if edited in Excel
                    try:
                        existing_lead = self._repository.get_by_id(dup_lead_id)
                        if existing_lead:
                            updated = False
                            if lead.notes and lead.notes != existing_lead.notes:
                                existing_lead.notes = lead.notes
                                updated = True
                            if lead.status and lead.status != existing_lead.status and lead.status != LeadStatus.NEW:
                                existing_lead.status = lead.status
                                updated = True
                            if updated:
                                self._repository.update(existing_lead)
                    except Exception as ex:
                        logger.error(f"Error updating duplicate lead notes/status: {ex}")
                    continue

                self._repository.add(lead)
                success_count += 1

        except MissingRequiredColumnError:
            raise  # Re-raise file-level errors immediately (REQ-002)

        # REQ-008: Record import history
        history = ImportHistory(
            import_batch_id=batch_id,
            source_file_name=path.name,
            actor=self._actor,
            success_count=success_count,
            error_count=error_count,
            duplicate_count=duplicate_count,
        )
        self._repository.add_import_history(history)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        logger.info(
            "ImportLeadsFromFileUseCase completed",
            extra={
                "context": {
                    "import_batch_id": batch_id,
                    "success_count": success_count,
                    "error_count": error_count,
                    "duplicate_count": duplicate_count,
                    "elapsed_ms": round(elapsed_ms, 2),
                }
            },
        )

        return ImportResultDTO(
            import_batch_id=batch_id,
            source_file_name=path.name,
            success_count=success_count,
            error_count=error_count,
            duplicate_count=duplicate_count,
            row_errors=row_errors,
            executed_at=datetime.now(timezone.utc).isoformat(),
        )

    def _validate_columns(self, row_data: dict[str, str], batch_id: str) -> None:
        """Check that all required columns are present in the first data row.

        Args:
            row_data: Column name → value mapping from the first row.
            batch_id: Import batch UUID (for logging).

        Raises:
            MissingRequiredColumnError: If any required column is absent.
        """
        actual_columns = frozenset(k.strip().lower() for k in row_data.keys())
        missing = [
            col for col in REQUIRED_IMPORT_COLUMNS if col not in actual_columns
        ]
        if missing:
            logger.error(
                "Import aborted: missing required columns",
                extra={"context": {"missing": missing, "import_batch_id": batch_id}},
            )
            raise MissingRequiredColumnError(missing)

    def _build_lead(
        self,
        data: dict[str, str],
        batch_id: str,
        source_reference: str,
    ) -> Lead:
        """Construct and normalise a Lead from a raw row dictionary.

        Args:
            data: Raw field name → value mapping.
            batch_id: Import batch UUID.
            source_reference: Original file path.

        Returns:
            Normalised Lead entity.

        Raises:
            DomainError: On any field-level validation failure.
        """
        email_raw = data.get("email", "").strip()
        if email_raw:
            email_vo = normalize_email(email_raw)
            email_val = email_vo.value
        else:
            email_val = ""

        phone_vo = normalize_phone(data.get("phone", ""))
        company_vo = normalize_company_name(data.get("company_name", ""))

        # Optional: website and address normalisation (errors are non-fatal here
        # since they are caught in the caller's try/except DomainError block)
        website_raw = data.get("website", "").strip()
        try:
            website_str = normalize_website(website_raw).value if website_raw else ""
        except DomainError:
            website_str = website_raw  # Keep raw if invalid, don't block import

        contact_raw = data.get("contact_name", "").strip()
        try:
            contact_str = normalize_contact_name(contact_raw) if contact_raw else ""
        except DomainError:
            contact_str = contact_raw

        status_raw = data.get("status", "").strip()
        status_val = LeadStatus.NEW
        notes_val = data.get("notes", "").strip()

        if status_raw:
            status_upper = status_raw.upper()
            status_map = {
                "MỚI": LeadStatus.NEW,
                "NEW": LeadStatus.NEW,
                "ĐÃ LIÊN HỆ": LeadStatus.CONTACTED,
                "CONTACTED": LeadStatus.CONTACTED,
                "ĐÃ XÁC THỰC": LeadStatus.VALIDATED,
                "VALIDATED": LeadStatus.VALIDATED,
                "TIỀM NĂNG": LeadStatus.QUALIFIED,
                "QUALIFIED": LeadStatus.QUALIFIED,
                "ĐÃ CHỐT": LeadStatus.CONVERTED,
                "CONVERTED": LeadStatus.CONVERTED,
                "BỊ TỪ CHỐI": LeadStatus.REJECTED,
                "REJECTED": LeadStatus.REJECTED,
                "TRÙNG LẶP": LeadStatus.DUPLICATE,
                "DUPLICATE": LeadStatus.DUPLICATE,
            }
            if status_upper in status_map:
                status_val = status_map[status_upper]
            else:
                # If it's a custom note (e.g. "cúp máy", "ko bắt máy", "ko liên lạc được")
                # Store it in notes and mark status as CONTACTED (Đã liên hệ/đã gọi điện)
                if not notes_val:
                    notes_val = status_raw
                status_val = LeadStatus.CONTACTED

        try:
            score_raw = data.get("score", "0").strip()
            score_val = int(float(score_raw)) if score_raw else 0
        except Exception:
            score_val = 0

        return Lead(
            company_name=company_vo.value,
            contact_name=contact_str,
            email=email_val,
            phone=phone_vo.value,
            website=website_str,
            address=normalize_address(data.get("address", "")),
            source=self._adapter.source_type,
            source_reference=source_reference,
            status=status_val,
            score=score_val,
            notes=notes_val,
            import_batch_id=batch_id,
            phone_normalized=phone_vo.normalized,
        )

    def _find_duplicate(self, lead: Lead) -> Optional[str]:
        """Return the ID of an existing lead if a duplicate is detected.

        Args:
            lead: The newly built Lead entity to check.

        Returns:
            Existing lead's ID if it is a duplicate, None otherwise.
        """
        if self._dedup_config.use_email_dedup and lead.email:
            key = compute_email_dedup_key(lead.email)
            existing = self._repository.find_by_email(key)
            if existing is not None:
                return existing.id

        if self._dedup_config.use_company_phone_dedup and lead.company_name and lead.phone:
            _, phone_digits = compute_company_phone_dedup_key(
                lead.company_name, lead.phone
            )
            candidates = self._repository.find_duplicates(
                company_name=lead.company_name.lower(),
                phone=phone_digits,
            )
            if candidates:
                return candidates[0].id

        return None


def _infer_field_from_error(exc: DomainError) -> str:
    """Infer which field caused a DomainError from its error_code.

    Args:
        exc: The DomainError that was raised.

    Returns:
        Field name string, or 'unknown'.
    """
    code_to_field: dict[str, str] = {
        "INVALID_EMAIL_FORMAT": "email",
        "INVALID_PHONE_FORMAT": "phone",
        "INVALID_WEBSITE": "website",
        "INVALID_COMPANY_NAME": "company_name",
    }
    return code_to_field.get(exc.error_code, "unknown")
