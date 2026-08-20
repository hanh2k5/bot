"""LeadRepository port (interface) — Application layer.

Defines the abstract contract that all lead persistence adapters must satisfy
(REQ-030, ARCH-007). Implements the Dependency Inversion Principle.
The concrete implementation lives in the Infrastructure layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from leadhunter.domain.entities.lead import (
    DuplicateLog,
    ExportHistory,
    ImportHistory,
    Lead,
    LeadStatus,
    LeadStatusHistory,
)


class LeadRepository(ABC):
    """Abstract repository for Lead persistence (REQ-030).

    All methods must be implemented by the concrete infrastructure adapter.
    No method here may contain SQL, file I/O, or framework-specific code.
    """

    @abstractmethod
    def add(self, lead: Lead) -> Lead:
        """Persist a new lead record.

        Args:
            lead: The Lead entity to store.

        Returns:
            The persisted Lead (with any server-side defaults applied).

        Raises:
            DatabaseError: On persistence failure.
        """
        ...

    @abstractmethod
    def get_by_id(self, lead_id: str) -> Optional[Lead]:
        """Retrieve a lead by its unique ID.

        Args:
            lead_id: UUID string of the lead.

        Returns:
            The Lead entity, or None if not found.

        Raises:
            DatabaseError: On query failure.
        """
        ...

    @abstractmethod
    def find_by_email(self, email: str) -> Optional[Lead]:
        """Find a lead by its normalised email address.

        Args:
            email: Normalised (lowercase) email string.

        Returns:
            The Lead entity, or None if not found.

        Raises:
            DatabaseError: On query failure.
        """
        ...

    @abstractmethod
    def find_duplicates(
        self,
        email: Optional[str] = None,
        company_name: Optional[str] = None,
        phone: Optional[str] = None,
        url: Optional[str] = None,
    ) -> list[Lead]:
        """Find existing leads that match dedup criteria (REQ-027).

        Uses indexed queries — does NOT load the entire table into memory.

        Args:
            email: Normalised email to search for (optional).
            company_name: Normalised company name to search for (optional).
            phone: Normalised phone digits to search for (optional).

        Returns:
            List of matching Lead entities (empty if none found).

        Raises:
            DatabaseError: On query failure.
        """
        ...

    @abstractmethod
    def update(self, lead: Lead) -> Lead:
        """Update an existing lead record.

        Args:
            lead: The Lead entity with updated fields.

        Returns:
            The updated Lead entity.

        Raises:
            DatabaseError: On persistence failure.
            LeadNotFoundError: If the lead ID does not exist.
        """
        ...

    @abstractmethod
    def list(
        self,
        *,
        status: Optional[LeadStatus] = None,
        score_min: Optional[int] = None,
        score_max: Optional[int] = None,
        source: Optional[str] = None,
        keyword: Optional[str] = None,
        created_from: Optional[str] = None,
        created_to: Optional[str] = None,
        include_duplicates: bool = False,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[Lead]:
        """Query leads with filtering, sorting, and pagination (REQ-043-048).

        Args:
            status: Filter by exact status.
            score_min: Minimum score (inclusive).
            score_max: Maximum score (inclusive).
            source: Filter by source identifier.
            keyword: Full-text keyword against company_name, contact_name, email.
            created_from: ISO 8601 date-time lower bound for created_at.
            created_to: ISO 8601 date-time upper bound for created_at.
            include_duplicates: If False (default), exclude DUPLICATE status leads.
            page: 1-based page number.
            page_size: Number of records per page.
            sort_by: Field name to sort by.
            sort_order: 'asc' or 'desc'.

        Returns:
            Paginated list of Lead entities.

        Raises:
            DatabaseError: On query failure.
        """
        ...

    @abstractmethod
    def count(
        self,
        *,
        status: Optional[LeadStatus] = None,
        score_min: Optional[int] = None,
        score_max: Optional[int] = None,
        source: Optional[str] = None,
        keyword: Optional[str] = None,
        created_from: Optional[str] = None,
        created_to: Optional[str] = None,
        include_duplicates: bool = False,
    ) -> int:
        """Count leads matching the given filter criteria (REQ-047).

        Args:
            status: Filter by exact status.
            score_min: Minimum score (inclusive).
            score_max: Maximum score (inclusive).
            source: Filter by source identifier.
            keyword: Keyword to match against company_name, contact_name, email.
            created_from: ISO 8601 date-time lower bound for created_at.
            created_to: ISO 8601 date-time upper bound for created_at.
            include_duplicates: If False (default), exclude DUPLICATE status leads.

        Returns:
            Total matching record count.

        Raises:
            DatabaseError: On query failure.
        """
        ...

    @abstractmethod
    def add_status_history(self, history: LeadStatusHistory) -> None:
        """Record a status transition for a lead (REQ-037).

        Args:
            history: The status history record to persist.

        Raises:
            DatabaseError: On persistence failure.
        """
        ...

    @abstractmethod
    def get_status_history(self, lead_id: str) -> list[LeadStatusHistory]:
        """Retrieve the full status history for a lead (REQ-039).

        Args:
            lead_id: UUID of the lead.

        Returns:
            Chronological list of LeadStatusHistory records.

        Raises:
            DatabaseError: On query failure.
        """
        ...

    @abstractmethod
    def add_duplicate_log(self, log: DuplicateLog) -> None:
        """Log a detected duplicate during ingestion (REQ-025).

        Args:
            log: The DuplicateLog record.

        Raises:
            DatabaseError: On persistence failure.
        """
        ...

    @abstractmethod
    def add_import_history(self, history: ImportHistory) -> None:
        """Persist an import batch history record (REQ-008).

        Args:
            history: The ImportHistory record.

        Raises:
            DatabaseError: On persistence failure.
        """
        ...

    @abstractmethod
    def add_export_history(self, history: ExportHistory) -> None:
        """Persist an export operation history record (REQ-061).

        Args:
            history: The ExportHistory record.

        Raises:
            DatabaseError: On persistence failure.
        """
        ...

    @abstractmethod
    def list_all_for_export(
        self,
        *,
        status: Optional[LeadStatus] = None,
        score_min: Optional[int] = None,
        score_max: Optional[int] = None,
        source: Optional[str] = None,
        keyword: Optional[str] = None,
        created_from: Optional[str] = None,
        created_to: Optional[str] = None,
        batch_size: int = 500,
    ) -> list[Lead]:
        """Retrieve all matching leads for export, in batches (REQ-058).

        Yields results in batches to avoid loading the entire table into memory.
        Callers should treat the returned list as a complete snapshot.

        Args:
            status: Filter by exact status.
            score_min: Minimum score.
            score_max: Maximum score.
            source: Source identifier filter.
            keyword: Keyword filter.
            created_from: ISO 8601 lower bound.
            created_to: ISO 8601 upper bound.
            batch_size: Internal fetch batch size (caller-transparent).

        Returns:
            Complete list of matching Lead entities.

        Raises:
            DatabaseError: On query failure.
        """
        ...
