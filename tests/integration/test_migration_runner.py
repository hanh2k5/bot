"""Integration tests for MigrationRunner (REQ-033)."""

from __future__ import annotations

import pytest

from leadhunter.infrastructure.persistence.connection_manager import ConnectionManager
from leadhunter.infrastructure.persistence.migrations.migration_runner import MigrationRunner


class TestMigrationRunner:
    """Tests for database migration runner."""

    def test_first_run_applies_migrations(self, in_memory_conn: ConnectionManager) -> None:
        """First run applies all migrations and returns their versions."""
        runner = MigrationRunner(in_memory_conn)
        applied = runner.run()
        assert 1 in applied  # Migration 001 applied

    def test_second_run_is_idempotent(self, in_memory_conn: ConnectionManager) -> None:
        """Second run applies no migrations (idempotent)."""
        runner = MigrationRunner(in_memory_conn)
        runner.run()
        applied_second = runner.run()
        assert applied_second == []

    def test_schema_migrations_table_exists(self, in_memory_conn: ConnectionManager) -> None:
        """schema_migrations table is created by the runner."""
        runner = MigrationRunner(in_memory_conn)
        runner.run()
        with in_memory_conn.connection() as conn:
            row = conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
        assert row[0] == 1

    def test_leads_table_exists_after_migration(self, in_memory_conn: ConnectionManager) -> None:
        """Leads table is created by migration 001."""
        runner = MigrationRunner(in_memory_conn)
        runner.run()
        with in_memory_conn.connection() as conn:
            row = conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='leads'"
            ).fetchone()
        assert row[0] == 1

    def test_all_required_tables_exist(self, in_memory_conn: ConnectionManager) -> None:
        """All tables defined in 001_initial_schema.sql are created."""
        runner = MigrationRunner(in_memory_conn)
        runner.run()
        required_tables = [
            "leads",
            "import_history",
            "duplicate_log",
            "lead_status_history",
            "export_history",
            "schema_migrations",
        ]
        with in_memory_conn.connection() as conn:
            for table_name in required_tables:
                row = conn.execute(
                    "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,)
                ).fetchone()
                assert row[0] == 1, f"Table '{table_name}' not found"
