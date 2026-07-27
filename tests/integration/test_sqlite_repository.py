"""Integration tests for SqliteLeadRepository (REQ-031 through REQ-035)."""

from __future__ import annotations

import pytest

from leadhunter.domain.entities.lead import Lead, LeadStatus, LeadStatusHistory
from leadhunter.infrastructure.persistence.sqlite_lead_repository import SqliteLeadRepository


def _make_lead(
    company_name: str = "Test Corp",
    email: str = "test@example.com",
    **kwargs,
) -> Lead:
    """Factory helper for test leads."""
    return Lead(
        company_name=company_name,
        contact_name="Test User",
        email=email,
        phone="+84912345678",
        website="https://test.com",
        address="123 Test St",
        source="excel",
        source_reference="test.xlsx",
        **kwargs,
    )


class TestAddAndGetById:
    """Tests for add() and get_by_id() (REQ-030)."""

    def test_add_and_retrieve_lead(self, migrated_repo: SqliteLeadRepository) -> None:
        """Lead can be added and retrieved by ID."""
        lead = _make_lead()
        migrated_repo.add(lead)
        retrieved = migrated_repo.get_by_id(lead.id)
        assert retrieved is not None
        assert retrieved.id == lead.id
        assert retrieved.email == lead.email

    def test_get_by_id_missing_returns_none(self, migrated_repo: SqliteLeadRepository) -> None:
        """get_by_id returns None for unknown ID."""
        result = migrated_repo.get_by_id("nonexistent-uuid")
        assert result is None

    def test_add_preserves_all_fields(self, migrated_repo: SqliteLeadRepository) -> None:
        """All Lead fields are persisted correctly."""
        lead = _make_lead(notes="Important lead", score=75, phone_normalized=True)
        migrated_repo.add(lead)
        retrieved = migrated_repo.get_by_id(lead.id)
        assert retrieved.notes == "Important lead"
        assert retrieved.score == 75
        assert retrieved.phone_normalized is True


class TestFindByEmail:
    """Tests for find_by_email() dedup (REQ-027, REQ-030)."""

    def test_find_by_email_returns_lead(self, migrated_repo: SqliteLeadRepository) -> None:
        """find_by_email returns the matching lead."""
        lead = _make_lead(email="unique@example.com")
        migrated_repo.add(lead)
        found = migrated_repo.find_by_email("unique@example.com")
        assert found is not None
        assert found.id == lead.id

    def test_find_by_email_missing_returns_none(self, migrated_repo: SqliteLeadRepository) -> None:
        """find_by_email returns None when email doesn't exist."""
        assert migrated_repo.find_by_email("nope@example.com") is None


class TestUpdate:
    """Tests for update() (REQ-030)."""

    def test_update_status(self, migrated_repo: SqliteLeadRepository) -> None:
        """Lead status is updated correctly."""
        lead = _make_lead()
        migrated_repo.add(lead)
        lead.status = LeadStatus.VALIDATED
        lead.touch()
        migrated_repo.update(lead)
        retrieved = migrated_repo.get_by_id(lead.id)
        assert retrieved.status == LeadStatus.VALIDATED

    def test_update_score(self, migrated_repo: SqliteLeadRepository) -> None:
        """Lead score is updated correctly."""
        lead = _make_lead()
        migrated_repo.add(lead)
        lead.score = 85
        lead.touch()
        migrated_repo.update(lead)
        retrieved = migrated_repo.get_by_id(lead.id)
        assert retrieved.score == 85


class TestListAndCount:
    """Tests for list() and count() with filtering (REQ-043-048)."""

    def test_list_returns_leads(self, migrated_repo: SqliteLeadRepository) -> None:
        """list() returns added leads."""
        for i in range(5):
            migrated_repo.add(_make_lead(email=f"lead{i}@example.com"))
        leads = migrated_repo.list()
        assert len(leads) == 5

    def test_list_pagination(self, migrated_repo: SqliteLeadRepository) -> None:
        """Pagination returns correct subset."""
        for i in range(10):
            migrated_repo.add(_make_lead(email=f"paged{i}@example.com"))
        page1 = migrated_repo.list(page=1, page_size=5)
        page2 = migrated_repo.list(page=2, page_size=5)
        assert len(page1) == 5
        assert len(page2) == 5
        ids1 = {l.id for l in page1}
        ids2 = {l.id for l in page2}
        assert ids1.isdisjoint(ids2)

    def test_count_matches_total(self, migrated_repo: SqliteLeadRepository) -> None:
        """count() returns correct total (REQ-047)."""
        for i in range(7):
            migrated_repo.add(_make_lead(email=f"cnt{i}@example.com"))
        assert migrated_repo.count() == 7

    def test_filter_by_status(self, migrated_repo: SqliteLeadRepository) -> None:
        """Filtering by status works correctly."""
        lead1 = _make_lead(email="a@example.com")
        lead2 = _make_lead(email="b@example.com")
        migrated_repo.add(lead1)
        migrated_repo.add(lead2)
        lead2.status = LeadStatus.VALIDATED
        migrated_repo.update(lead2)
        results = migrated_repo.list(status=LeadStatus.VALIDATED)
        assert len(results) == 1
        assert results[0].id == lead2.id

    def test_default_excludes_duplicates(self, migrated_repo: SqliteLeadRepository) -> None:
        """REQ-029: DUPLICATE leads excluded from default query."""
        lead1 = _make_lead(email="dup1@example.com")
        lead2 = _make_lead(email="dup2@example.com")
        migrated_repo.add(lead1)
        migrated_repo.add(lead2)
        lead2.status = LeadStatus.DUPLICATE
        migrated_repo.update(lead2)
        results = migrated_repo.list()
        assert all(l.status != LeadStatus.DUPLICATE for l in results)


class TestStatusHistory:
    """Tests for status history tracking (REQ-037, REQ-039)."""

    def test_add_and_retrieve_status_history(self, migrated_repo: SqliteLeadRepository) -> None:
        """Status history is recorded and retrieved."""
        lead = _make_lead()
        migrated_repo.add(lead)
        history = LeadStatusHistory(
            lead_id=lead.id,
            old_status=LeadStatus.NEW,
            new_status=LeadStatus.VALIDATED,
            actor="test",
        )
        migrated_repo.add_status_history(history)
        records = migrated_repo.get_status_history(lead.id)
        assert len(records) == 1
        assert records[0].new_status == LeadStatus.VALIDATED
