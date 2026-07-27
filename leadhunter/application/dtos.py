"""Application layer DTOs (Data Transfer Objects).

DTOs carry data between layers without business logic.
They are the data contract between Presentation ↔ Application.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Lead DTOs
# ---------------------------------------------------------------------------


@dataclass
class LeadDTO:
    """Snapshot of a lead for read operations (returned by use cases).

    Attributes:
        id: UUID string of the lead.
        company_name: Normalised company name.
        contact_name: Contact person's name.
        email: Normalised email.
        phone: Normalised phone.
        website: Normalised website URL.
        address: Normalised address.
        source: Source type identifier.
        source_reference: Original file or URL.
        status: Lead lifecycle status string.
        score: Integer score 0–100.
        notes: Free-text notes.
        created_at: ISO 8601 UTC timestamp string.
        updated_at: ISO 8601 UTC timestamp string.
        import_batch_id: UUID of the originating import batch.
        phone_normalized: Whether phone was normalised to E.164.
    """

    id: str
    company_name: str
    contact_name: str
    email: str
    phone: str
    website: str
    address: str
    source: str
    source_reference: str
    status: str
    score: int
    notes: str
    created_at: str
    updated_at: str
    import_batch_id: Optional[str] = None
    phone_normalized: bool = False


# ---------------------------------------------------------------------------
# Import DTOs
# ---------------------------------------------------------------------------


@dataclass
class ImportRowErrorDTO:
    """Error detail for a single row that failed during import.

    Attributes:
        row_index: 1-based row number in the source file.
        field: The field that caused the error.
        error_code: Stable error code string.
        message: Human-readable error description.
    """

    row_index: int
    field: str
    error_code: str
    message: str


@dataclass
class ImportResultDTO:
    """Summary result returned by ImportLeadsFromFileUseCase (REQ-001).

    Attributes:
        import_batch_id: UUID for this import batch.
        source_file_name: Name of the imported file.
        success_count: Number of records successfully imported.
        error_count: Number of rows that failed validation.
        duplicate_count: Number of rows detected as duplicates.
        row_errors: Detailed list of per-row errors.
        executed_at: ISO 8601 UTC timestamp of import start.
    """

    import_batch_id: str
    source_file_name: str
    success_count: int
    error_count: int
    duplicate_count: int
    row_errors: list[ImportRowErrorDTO] = field(default_factory=list)
    executed_at: str = ""


# ---------------------------------------------------------------------------
# Scrape DTOs
# ---------------------------------------------------------------------------


@dataclass
class ScrapeUrlErrorDTO:
    """Error detail for a single URL that failed during scraping.

    Attributes:
        url: The URL that failed.
        error_code: Stable error code string.
        message: Human-readable description.
        retry_count: Number of retry attempts made.
    """

    url: str
    error_code: str
    message: str
    retry_count: int = 0


@dataclass
class ScrapeResultDTO:
    """Summary result returned by ScrapeLeadsFromUrlsUseCase (REQ-009).

    Attributes:
        import_batch_id: UUID for this scrape batch.
        success_count: Number of leads extracted and saved.
        error_count: Number of URLs that failed entirely.
        duplicate_count: Number of scraped leads that were duplicates.
        url_errors: Detailed list of per-URL errors.
        executed_at: ISO 8601 UTC timestamp.
    """

    import_batch_id: str
    success_count: int
    error_count: int
    duplicate_count: int
    url_errors: list[ScrapeUrlErrorDTO] = field(default_factory=list)
    executed_at: str = ""


# ---------------------------------------------------------------------------
# Search / Query DTOs
# ---------------------------------------------------------------------------


@dataclass
class SearchParamsDTO:
    """Input parameters for SearchLeadsUseCase (REQ-043-048).

    Attributes:
        status: Filter by lead status string.
        score_min: Minimum score (inclusive).
        score_max: Maximum score (inclusive).
        source: Source identifier filter.
        keyword: Full-text keyword for company_name, contact_name, email.
        created_from: ISO 8601 lower bound for created_at.
        created_to: ISO 8601 upper bound for created_at.
        include_duplicates: Include DUPLICATE-status leads (default False).
        page: 1-based page number (default 1).
        page_size: Records per page (default 20, max 200).
        sort_by: Field to sort by (default 'created_at').
        sort_order: 'asc' or 'desc' (default 'desc').
    """

    status: Optional[str] = None
    score_min: Optional[int] = None
    score_max: Optional[int] = None
    source: Optional[str] = None
    keyword: Optional[str] = None
    created_from: Optional[str] = None
    created_to: Optional[str] = None
    include_duplicates: bool = False
    page: int = 1
    page_size: int = 20
    sort_by: str = "created_at"
    sort_order: str = "desc"


@dataclass
class SearchResultDTO:
    """Paginated result from SearchLeadsUseCase (REQ-043-048).

    Attributes:
        leads: List of LeadDTOs on the current page.
        total_count: Total matching records (for pagination display, REQ-047).
        page: Current page number.
        page_size: Number of records per page.
    """

    leads: list[LeadDTO]
    total_count: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Status update DTOs
# ---------------------------------------------------------------------------


@dataclass
class UpdateStatusInputDTO:
    """Input for UpdateLeadStatusUseCase (REQ-036).

    Attributes:
        lead_id: UUID of the lead to update.
        new_status: Desired new status string.
        actor: Who is performing the update (e.g. 'cli').
        reason: Optional reason for the status change.
    """

    lead_id: str
    new_status: str
    actor: str
    reason: Optional[str] = None


@dataclass
class UpdateStatusResultDTO:
    """Result of UpdateLeadStatusUseCase (REQ-036).

    Attributes:
        lead_id: UUID of the updated lead.
        old_status: Previous status.
        new_status: New status after update.
        changed_at: ISO 8601 UTC timestamp of the change.
    """

    lead_id: str
    old_status: str
    new_status: str
    changed_at: str


# ---------------------------------------------------------------------------
# Scoring DTOs
# ---------------------------------------------------------------------------


@dataclass
class ScoreResultDTO:
    """Result of ScoreLeadUseCase / ScoreLeadsBatchUseCase (REQ-049-055).

    Attributes:
        lead_id: UUID of the scored lead.
        old_score: Score before this scoring run.
        new_score: Score after this scoring run.
        updated_at: ISO 8601 UTC timestamp of the score update.
    """

    lead_id: str
    old_score: int
    new_score: int
    updated_at: str


@dataclass
class BatchScoreResultDTO:
    """Aggregate result for ScoreLeadsBatchUseCase.

    Attributes:
        processed_count: Total leads processed.
        updated_count: Leads whose score actually changed.
        elapsed_ms: Time taken in milliseconds.
    """

    processed_count: int
    updated_count: int
    elapsed_ms: float


# ---------------------------------------------------------------------------
# Export DTOs
# ---------------------------------------------------------------------------


@dataclass
class ExportParamsDTO:
    """Input parameters for ExportLeadsToExcelUseCase (REQ-056-062).

    Attributes:
        output_path: Target file path (without extension; .xlsx appended).
        actor: Who initiated the export.
        status: Filter by status string.
        score_min: Minimum score filter.
        score_max: Maximum score filter.
        source: Source filter.
        keyword: Keyword filter.
        created_from: ISO 8601 lower bound.
        created_to: ISO 8601 upper bound.
    """

    output_path: Optional[str] = None  # If None, use default naming pattern
    actor: str = "cli"
    status: Optional[str] = None
    score_min: Optional[int] = None
    score_max: Optional[int] = None
    source: Optional[str] = None
    keyword: Optional[str] = None
    created_from: Optional[str] = None
    created_to: Optional[str] = None


@dataclass
class ExportResultDTO:
    """Result of ExportLeadsToExcelUseCase (REQ-060).

    Attributes:
        output_file_path: Absolute path to the created .xlsx file.
        record_count: Number of records written to the file.
        executed_at: ISO 8601 UTC timestamp of export completion.
    """

    output_file_path: str
    record_count: int
    executed_at: str


# ---------------------------------------------------------------------------
# Merge DTOs
# ---------------------------------------------------------------------------


@dataclass
class MergeLeadInputDTO:
    """Input for MergeLeadUseCase (REQ-026).

    Attributes:
        duplicate_lead_id: UUID of the lead to be merged (the copy).
        target_lead_id: UUID of the canonical lead (to be kept/updated).
        actor: Who is performing the merge.
    """

    duplicate_lead_id: str
    target_lead_id: str
    actor: str


@dataclass
class MergeLeadResultDTO:
    """Result of MergeLeadUseCase (REQ-026).

    Attributes:
        target_lead_id: UUID of the canonical lead after merge.
        merged_at: ISO 8601 UTC timestamp.
        fields_updated: List of field names that were updated on the target.
    """

    target_lead_id: str
    merged_at: str
    fields_updated: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Status history DTO
# ---------------------------------------------------------------------------


@dataclass
class LeadStatusHistoryDTO:
    """DTO representing one entry in a lead's status history (REQ-039).

    Attributes:
        id: UUID of the history record.
        lead_id: UUID of the lead.
        old_status: Status before the transition.
        new_status: Status after the transition.
        changed_at: ISO 8601 UTC timestamp.
        actor: Who triggered the change.
        reason: Optional reason string.
    """

    id: str
    lead_id: str
    old_status: str
    new_status: str
    changed_at: str
    actor: str
    reason: Optional[str] = None
