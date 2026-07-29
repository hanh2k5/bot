"""Lead entity and LeadStatus enumeration.

Defines the core domain entity (AS-04) and the status workflow (AS-06).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class LeadStatus(str, Enum):
    """Enumeration of all valid lead lifecycle statuses (AS-06).

    Inherits from str so values can be compared directly with string literals
    and stored/retrieved from SQLite without extra conversion.
    """

    NEW = "NEW"
    VALIDATED = "VALIDATED"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    CONVERTED = "CONVERTED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"

    @classmethod
    def terminal_statuses(cls) -> frozenset["LeadStatus"]:
        """Return the set of terminal (no-outgoing-transition) statuses."""
        return frozenset({cls.CONVERTED, cls.REJECTED, cls.DUPLICATE})


@dataclass
class Lead:
    """Core domain entity representing a sales lead (AS-04).

    Attributes:
        id: Unique identifier (UUID string). Auto-generated if not provided.
        company_name: Normalised company name.
        contact_name: Name of the primary contact at the company.
        email: Normalised email address (string, already validated by VO).
        phone: Normalised phone number string.
        website: Normalised website URL string.
        address: Address (whitespace-normalised, no deep parsing in Phase 1).
        source: Source channel identifier ('excel', 'web').
        source_reference: Original filename or URL that produced this lead.
        status: Current lifecycle status.
        score: Integer score 0–100.
        notes: Free-text notes field.
        created_at: UTC timestamp of record creation.
        updated_at: UTC timestamp of last modification.
        import_batch_id: UUID of the ingestion batch that created this record.
        phone_normalized: True if phone was successfully normalised to E.164.
    """

    company_name: str
    contact_name: str
    email: str
    phone: str
    website: str
    address: str
    source: str
    source_reference: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: LeadStatus = LeadStatus.NEW
    score: int = 0
    notes: str = ""
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    import_batch_id: Optional[str] = None
    phone_normalized: bool = False

    def touch(self) -> None:
        """Update the ``updated_at`` timestamp to now (UTC)."""
        self.updated_at = datetime.now(timezone.utc)


@dataclass
class LeadStatusHistory:
    """Audit record of a single status transition for a lead (REQ-037).

    Attributes:
        id: Auto-generated UUID for this history record.
        lead_id: The lead this transition belongs to.
        old_status: Status before the transition.
        new_status: Status after the transition.
        changed_at: When the transition occurred (UTC).
        actor: Who or what triggered the transition (e.g. 'cli', 'system').
        reason: Optional free-text reason for the transition.
    """

    lead_id: str
    old_status: LeadStatus
    new_status: LeadStatus
    actor: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    changed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    reason: Optional[str] = None


@dataclass
class DuplicateLog:
    """Record of a detected duplicate during ingestion (REQ-025).

    Attributes:
        id: Auto-generated UUID.
        original_lead_id: ID of the existing (original) lead.
        duplicate_data: JSON-serialised raw data of the duplicate record.
        detected_at: When the duplicate was detected (UTC).
        import_batch_id: Batch that contained the duplicate.
    """

    original_lead_id: str
    duplicate_data: str  # JSON string
    import_batch_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    detected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ImportHistory:
    """Record of a single import batch operation (REQ-008).

    Attributes:
        import_batch_id: UUID of this import batch.
        source_file_name: Name of the source file.
        executed_at: When the import started (UTC).
        success_count: Number of records successfully imported.
        error_count: Number of records that failed validation.
        duplicate_count: Number of records detected as duplicates.
        actor: CLI user or process identifier.
    """

    import_batch_id: str
    source_file_name: str
    actor: str
    success_count: int = 0
    error_count: int = 0
    duplicate_count: int = 0
    executed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ExportHistory:
    """Record of a single export operation (REQ-061).

    Attributes:
        id: Auto-generated UUID.
        executed_at: When the export ran (UTC).
        filter_criteria: JSON string of applied filters.
        record_count: Number of records exported.
        output_file_path: Absolute or relative path to the generated file.
        actor: CLI user or process identifier.
    """

    filter_criteria: str  # JSON string
    record_count: int
    output_file_path: str
    actor: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    executed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
