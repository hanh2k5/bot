"""SqliteLeadRepository — Infrastructure layer (REQ-031 through REQ-035).

Concrete implementation of LeadRepository using SQLite.

Security:
  - All SQL uses parameterized queries (? placeholders). NO string concatenation
    of user input into SQL (REQ-031).
  - Returns only Domain entities/DTOs, never sqlite3 cursor/connection objects (REQ-035).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from leadhunter.application.ports.lead_repository import LeadRepository
from leadhunter.domain.entities.lead import (
    DuplicateLog,
    ExportHistory,
    ImportHistory,
    Lead,
    LeadStatus,
    LeadStatusHistory,
)
from leadhunter.domain.exceptions import DatabaseError, LeadNotFoundError
from leadhunter.infrastructure.persistence.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

# Whitelist of sortable fields to prevent SQL injection via sort_by param
_ALLOWED_SORT_FIELDS = frozenset(
    {"created_at", "score", "company_name", "updated_at", "email"}
)
_ALLOWED_SORT_ORDERS = frozenset({"asc", "desc"})


class SqliteLeadRepository(LeadRepository):
    """SQLite-backed LeadRepository (REQ-031 through REQ-035).

    Args:
        connection_manager: ConnectionManager providing database connections.
    """

    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._cm = connection_manager

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    def add(self, lead: Lead) -> Lead:
        """Persist a new Lead record (REQ-030).

        Args:
            lead: Lead entity to insert.

        Returns:
            The same Lead entity.

        Raises:
            DatabaseError: On any SQLite error.
        """
        try:
            with self._cm.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO leads (
                        id, company_name, contact_name, email, phone, website,
                        address, source, source_reference, status, score, notes,
                        created_at, updated_at, import_batch_id, phone_normalized
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lead.id,
                        lead.company_name,
                        lead.contact_name,
                        lead.email,
                        lead.phone,
                        lead.website,
                        lead.address,
                        lead.source,
                        lead.source_reference,
                        lead.status.value,
                        lead.score,
                        lead.notes,
                        lead.created_at.isoformat(),
                        lead.updated_at.isoformat(),
                        lead.import_batch_id,
                        1 if lead.phone_normalized else 0,
                    ),
                )
        except Exception as exc:
            raise DatabaseError("INSERT leads", exc) from exc
        return lead

    def rollback_last_batch(self) -> int:
        """Xóa toàn bộ lead thuộc về đợt cào (import_batch_id) gần nhất."""
        try:
            with self._cm.transaction() as conn:
                # Tìm import_batch_id mới nhất
                row = conn.execute(
                    "SELECT import_batch_id FROM leads WHERE import_batch_id IS NOT NULL ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                
                if not row or not row[0]:
                    return 0
                
                batch_id = row[0]
                
                # Xóa dữ liệu liên quan ở các bảng phụ thuộc trước (để tránh lỗi FK constraint)
                conn.execute(
                    "DELETE FROM duplicate_log WHERE import_batch_id = ? OR original_lead_id IN (SELECT id FROM leads WHERE import_batch_id = ?)",
                    (batch_id, batch_id),
                )
                conn.execute(
                    "DELETE FROM lead_status_history WHERE lead_id IN (SELECT id FROM leads WHERE import_batch_id = ?)",
                    (batch_id,),
                )
                conn.execute(
                    "DELETE FROM import_history WHERE import_batch_id = ?",
                    (batch_id,),
                )
                
                # Xóa tất cả lead có batch_id này
                cursor = conn.execute("DELETE FROM leads WHERE import_batch_id = ?", (batch_id,))
                return cursor.rowcount
        except Exception as exc:
            raise DatabaseError("ROLLBACK last batch", exc) from exc

    def get_by_id(self, lead_id: str) -> Optional[Lead]:
        """Retrieve a Lead by its UUID (REQ-030).

        Args:
            lead_id: UUID string.

        Returns:
            Lead entity or None.

        Raises:
            DatabaseError: On SQLite error.
        """
        try:
            with self._cm.connection() as conn:
                row = conn.execute(
                    "SELECT * FROM leads WHERE id = ?", (lead_id,)
                ).fetchone()
        except Exception as exc:
            raise DatabaseError("SELECT leads by id", exc) from exc

        return _row_to_lead(row) if row else None

    def find_by_email(self, email: str) -> Optional[Lead]:
        """Find a lead by normalised email address (REQ-030).

        Uses the idx_leads_email index for O(log n) lookup (REQ-027).

        Args:
            email: Normalised (lowercase) email.

        Returns:
            Lead entity or None.

        Raises:
            DatabaseError: On SQLite error.
        """
        try:
            with self._cm.connection() as conn:
                row = conn.execute(
                    "SELECT * FROM leads WHERE email = ? LIMIT 1", (email,)
                ).fetchone()
        except Exception as exc:
            raise DatabaseError("SELECT leads by email", exc) from exc
        return _row_to_lead(row) if row else None

    def find_duplicates(
        self,
        email: Optional[str] = None,
        company_name: Optional[str] = None,
        phone: Optional[str] = None,
        url: Optional[str] = None,
    ) -> list[Lead]:
        """Find leads matching dedup keys (REQ-027, REQ-030).

        Uses indexed columns. Does NOT load the full table (REQ-027).

        Args:
            email: Normalised email (optional).
            company_name: Lowercase company name (optional).
            phone: Digits-only phone (optional).
            url: Google Maps Place URL (optional).

        Returns:
            List of matching Lead entities.

        Raises:
            DatabaseError: On SQLite error.
        """
        try:
            with self._cm.connection() as conn:
                results: list[Lead] = []

                if url:
                    row = conn.execute(
                        "SELECT * FROM leads WHERE source_reference = ? LIMIT 1", (url,)
                    ).fetchone()
                    if row:
                        results.append(_row_to_lead(row))

                if email and not results:
                    row = conn.execute(
                        "SELECT * FROM leads WHERE email = ? LIMIT 1", (email,)
                    ).fetchone()
                    if row:
                        results.append(_row_to_lead(row))

                if phone and not results:
                    cleaned_phone = phone.replace(" ", "").replace("-", "").replace("+", "")
                    last_9 = cleaned_phone[-9:] if len(cleaned_phone) >= 9 else cleaned_phone
                    rows = conn.execute(
                        """
                        SELECT * FROM leads
                        WHERE SUBSTR(replace(replace(replace(phone, ' ', ''),'-',''),'+',''), -9) = ?
                        LIMIT 5
                        """,
                        (last_9,),
                    ).fetchall()
                    results.extend(_row_to_lead(r) for r in rows)
        except Exception as exc:
            raise DatabaseError("SELECT find_duplicates", exc) from exc
        return results

    def update(self, lead: Lead) -> Lead:
        """Update an existing lead record (REQ-030).

        Args:
            lead: Lead entity with updated fields.

        Returns:
            The updated Lead.

        Raises:
            DatabaseError: On SQLite error.
            LeadNotFoundError: If the lead does not exist.
        """
        try:
            with self._cm.transaction() as conn:
                cursor = conn.execute(
                    """
                    UPDATE leads SET
                        company_name = ?, contact_name = ?, email = ?,
                        phone = ?, website = ?, address = ?,
                        status = ?, score = ?, notes = ?,
                        updated_at = ?, phone_normalized = ?
                    WHERE id = ?
                    """,
                    (
                        lead.company_name,
                        lead.contact_name,
                        lead.email,
                        lead.phone,
                        lead.website,
                        lead.address,
                        lead.status.value,
                        lead.score,
                        lead.notes,
                        lead.updated_at.isoformat(),
                        1 if lead.phone_normalized else 0,
                        lead.id,
                    ),
                )
                if cursor.rowcount == 0:
                    raise LeadNotFoundError(lead.id)
        except LeadNotFoundError:
            raise
        except Exception as exc:
            raise DatabaseError("UPDATE leads", exc) from exc
        return lead

    # ------------------------------------------------------------------
    # List / Count
    # ------------------------------------------------------------------

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
        """Paginated, sorted, filtered lead query (REQ-043-048).

        Args:
            status: Filter by status.
            score_min: Minimum score.
            score_max: Maximum score.
            source: Source filter.
            keyword: Keyword search on company_name, contact_name, email.
            created_from: ISO 8601 lower bound.
            created_to: ISO 8601 upper bound.
            include_duplicates: Include DUPLICATE status records.
            page: 1-based page.
            page_size: Records per page.
            sort_by: Column to sort by.
            sort_order: 'asc' or 'desc'.

        Returns:
            List of Lead entities for the requested page.

        Raises:
            DatabaseError: On SQLite error.
        """
        where, params = _build_where_clause(
            status, score_min, score_max, source, keyword,
            created_from, created_to, include_duplicates
        )
        # Security: validate sort_by against whitelist before embedding in SQL
        safe_sort = sort_by if sort_by in _ALLOWED_SORT_FIELDS else "created_at"
        safe_order = sort_order if sort_order in _ALLOWED_SORT_ORDERS else "desc"
        offset = (page - 1) * page_size
        sql = (
            f"SELECT * FROM leads {where} "
            f"ORDER BY {safe_sort} {safe_order.upper()} "
            f"LIMIT ? OFFSET ?"
        )
        params.extend([page_size, offset])

        try:
            with self._cm.connection() as conn:
                rows = conn.execute(sql, params).fetchall()
        except Exception as exc:
            raise DatabaseError("SELECT list leads", exc) from exc
        return [_row_to_lead(r) for r in rows]

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
        """Count leads matching filters (REQ-047).

        Args:
            (same filter args as list())

        Returns:
            Total matching record count.

        Raises:
            DatabaseError: On SQLite error.
        """
        where, params = _build_where_clause(
            status, score_min, score_max, source, keyword,
            created_from, created_to, include_duplicates
        )
        sql = f"SELECT COUNT(*) FROM leads {where}"
        try:
            with self._cm.connection() as conn:
                row = conn.execute(sql, params).fetchone()
        except Exception as exc:
            raise DatabaseError("COUNT leads", exc) from exc
        return row[0] if row else 0

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
        """Retrieve all matching leads in batches for export (REQ-058).

        Args:
            batch_size: Internal pagination batch size.

        Returns:
            Complete list of matching Lead entities.

        Raises:
            DatabaseError: On SQLite error.
        """
        all_leads: list[Lead] = []
        page = 1
        while True:
            batch = self.list(
                status=status,
                score_min=score_min,
                score_max=score_max,
                source=source,
                keyword=keyword,
                created_from=created_from,
                created_to=created_to,
                include_duplicates=False,
                page=page,
                page_size=batch_size,
                sort_by="created_at",
                sort_order="asc",
            )
            if not batch:
                break
            all_leads.extend(batch)
            page += 1
        return all_leads

    # ------------------------------------------------------------------
    # History / Audit
    # ------------------------------------------------------------------

    def add_status_history(self, history: LeadStatusHistory) -> None:
        """Record a status transition (REQ-037).

        Args:
            history: LeadStatusHistory record to persist.

        Raises:
            DatabaseError: On SQLite error.
        """
        try:
            with self._cm.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO lead_status_history
                        (id, lead_id, old_status, new_status, changed_at, actor, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        history.id,
                        history.lead_id,
                        history.old_status.value,
                        history.new_status.value,
                        history.changed_at.isoformat(),
                        history.actor,
                        history.reason,
                    ),
                )
        except Exception as exc:
            raise DatabaseError("INSERT lead_status_history", exc) from exc

    def get_status_history(self, lead_id: str) -> list[LeadStatusHistory]:
        """Retrieve chronological status history for a lead (REQ-039).

        Args:
            lead_id: UUID of the lead.

        Returns:
            Ordered list of LeadStatusHistory records.

        Raises:
            DatabaseError: On SQLite error.
        """
        try:
            with self._cm.connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM lead_status_history
                    WHERE lead_id = ?
                    ORDER BY changed_at ASC
                    """,
                    (lead_id,),
                ).fetchall()
        except Exception as exc:
            raise DatabaseError("SELECT lead_status_history", exc) from exc

        return [
            LeadStatusHistory(
                id=r["id"],
                lead_id=r["lead_id"],
                old_status=LeadStatus(r["old_status"]),
                new_status=LeadStatus(r["new_status"]),
                changed_at=datetime.fromisoformat(r["changed_at"]),
                actor=r["actor"],
                reason=r["reason"],
            )
            for r in rows
        ]

    def add_duplicate_log(self, log: DuplicateLog) -> None:
        """Log a detected duplicate record (REQ-025).

        Args:
            log: DuplicateLog record.

        Raises:
            DatabaseError: On SQLite error.
        """
        try:
            with self._cm.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO duplicate_log
                        (id, original_lead_id, duplicate_data, detected_at, import_batch_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        log.id,
                        log.original_lead_id,
                        log.duplicate_data,
                        log.detected_at.isoformat(),
                        log.import_batch_id,
                    ),
                )
        except Exception as exc:
            raise DatabaseError("INSERT duplicate_log", exc) from exc

    def add_import_history(self, history: ImportHistory) -> None:
        """Persist an import batch history record (REQ-008).

        Args:
            history: ImportHistory record.

        Raises:
            DatabaseError: On SQLite error.
        """
        try:
            with self._cm.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO import_history
                        (import_batch_id, source_file_name, executed_at,
                         success_count, error_count, duplicate_count, actor)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        history.import_batch_id,
                        history.source_file_name,
                        history.executed_at.isoformat(),
                        history.success_count,
                        history.error_count,
                        history.duplicate_count,
                        history.actor,
                    ),
                )
        except Exception as exc:
            raise DatabaseError("INSERT import_history", exc) from exc

    def add_export_history(self, history: ExportHistory) -> None:
        """Persist an export history record (REQ-061).

        Args:
            history: ExportHistory record.

        Raises:
            DatabaseError: On SQLite error.
        """
        try:
            with self._cm.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO export_history
                        (id, executed_at, filter_criteria, record_count,
                         output_file_path, actor)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        history.id,
                        history.executed_at.isoformat(),
                        history.filter_criteria,
                        history.record_count,
                        history.output_file_path,
                        history.actor,
                    ),
                )
        except Exception as exc:
            raise DatabaseError("INSERT export_history", exc) from exc


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_where_clause(
    status: Optional[LeadStatus],
    score_min: Optional[int],
    score_max: Optional[int],
    source: Optional[str],
    keyword: Optional[str],
    created_from: Optional[str],
    created_to: Optional[str],
    include_duplicates: bool,
) -> tuple[str, list]:
    """Build a parameterized WHERE clause for lead queries.

    All values go through parameter binding — never string concatenation
    of user-controlled data (REQ-031, security).

    Args:
        (same as list() / count() filter args)

    Returns:
        Tuple of (WHERE clause string, parameters list).
    """
    conditions: list[str] = []
    params: list = []

    if status is not None:
        conditions.append("status = ?")
        params.append(status.value)
    elif not include_duplicates:
        # REQ-029: Exclude DUPLICATE by default
        conditions.append("status != ?")
        params.append(LeadStatus.DUPLICATE.value)

    if score_min is not None:
        conditions.append("score >= ?")
        params.append(score_min)
    if score_max is not None:
        conditions.append("score <= ?")
        params.append(score_max)
    if source is not None:
        conditions.append("source = ?")
        params.append(source)
    if keyword is not None:
        like_term = f"%{keyword}%"
        conditions.append(
            "(company_name LIKE ? OR contact_name LIKE ? OR email LIKE ?)"
        )
        params.extend([like_term, like_term, like_term])
    if created_from is not None:
        conditions.append("created_at >= ?")
        params.append(created_from)
    if created_to is not None:
        conditions.append("created_at <= ?")
        params.append(created_to)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    return where, params


def _row_to_lead(row: object) -> Lead:
    """Convert a sqlite3.Row to a Lead domain entity.

    Args:
        row: sqlite3.Row from the leads table.

    Returns:
        Lead entity.
    """
    return Lead(
        id=row["id"],
        company_name=row["company_name"],
        contact_name=row["contact_name"],
        email=row["email"],
        phone=row["phone"],
        website=row["website"],
        address=row["address"],
        source=row["source"],
        source_reference=row["source_reference"],
        status=LeadStatus(row["status"]),
        score=row["score"],
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        import_batch_id=row["import_batch_id"],
        phone_normalized=bool(row["phone_normalized"]),
    )
