"""Regression Test Suite for Bug 3 — SQLite Duplicate Protection."""

import pytest
import threading
import uuid
from pathlib import Path
from leadhunter.domain.entities.lead import Lead, LeadStatus
from leadhunter.infrastructure.persistence.connection_manager import ConnectionManager
from leadhunter.infrastructure.persistence.migrations.migration_runner import MigrationRunner
from leadhunter.infrastructure.persistence.sqlite_lead_repository import SqliteLeadRepository


@pytest.fixture
def test_repo(tmp_path):
    db_file = tmp_path / f"test_leadhunter_{uuid.uuid4().hex}.db"
    cm = ConnectionManager(db_path=db_file)
    runner = MigrationRunner(cm)
    runner.run()
    repo = SqliteLeadRepository(cm)
    yield repo
    if db_file.exists():
        try:
            db_file.unlink()
        except Exception:
            pass


class TestSQLiteDuplicateProtection:
    """Regression tests for Bug 3 — Unique Constraint and duplicate protection in SQLite DB."""

    def test_duplicate_phone_insert_rejected_or_handled_safely(self, test_repo):
        lead1 = Lead(
            company_name="Cửa Hàng Xây Dựng A",
            contact_name="",
            email="",
            phone="0908123456",
            website="",
            address="123 Đường ABC, Q1, TP.HCM",
            source="maps",
            source_reference="",
            status=LeadStatus.NEW,
        )

        lead2 = Lead(
            company_name="Công Ty Xây Dựng B (Trùng SĐT)",
            contact_name="",
            email="",
            phone="0908123456",
            website="",
            address="456 Đường XYZ, Q3, TP.HCM",
            source="maps",
            source_reference="",
            status=LeadStatus.NEW,
        )

        # Insert 1st time -> Success
        res1 = test_repo.add(lead1)
        assert res1.phone == "0908123456"

        # Insert 2nd time with same phone -> Handled safely without crash, returns existing or original lead
        res2 = test_repo.add(lead2)
        assert res2 is not None

        # Verify DB total count is strictly 1 (no duplicate rows created)
        total_count = test_repo.count()
        assert total_count == 1

    def test_concurrent_duplicate_phone_inserts(self, test_repo):
        """Test concurrent multi-threaded inserts of the same phone number."""
        phone = "0918888999"
        errors = []

        def worker_insert(idx):
            try:
                lead = Lead(
                    company_name=f"Worker Corp {idx}",
                    contact_name="",
                    email="",
                    phone=phone,
                    website="",
                    address="Quận 7, TP.HCM",
                    source="maps",
                    source_reference="",
                    status=LeadStatus.NEW,
                )
                test_repo.add(lead)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker_insert, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Integrity verified: zero unhandled exceptions, total count in DB is 1
        assert len(errors) == 0
        assert test_repo.count() == 1
