"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest

from leadhunter.infrastructure.persistence.connection_manager import ConnectionManager
from leadhunter.infrastructure.persistence.sqlite_lead_repository import SqliteLeadRepository
from leadhunter.infrastructure.persistence.migrations.migration_runner import MigrationRunner


@pytest.fixture
def in_memory_conn() -> ConnectionManager:
    """Provide an in-memory SQLite ConnectionManager for tests."""
    cm = ConnectionManager(":memory:")
    return cm


@pytest.fixture
def migrated_repo(in_memory_conn: ConnectionManager) -> SqliteLeadRepository:
    """Provide a fully migrated in-memory SqliteLeadRepository for integration tests."""
    runner = MigrationRunner(in_memory_conn)
    runner.run()
    return SqliteLeadRepository(in_memory_conn)
