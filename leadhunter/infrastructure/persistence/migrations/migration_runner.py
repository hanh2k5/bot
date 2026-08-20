"""Database migration runner — Infrastructure layer (REQ-033).

Discovers and applies pending SQL migrations at application startup.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from leadhunter.domain.exceptions import MigrationError
from leadhunter.infrastructure.persistence.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent


class MigrationRunner:
    """Applies pending database schema migrations at startup (REQ-033).

    Migrations are SQL files in the same directory, named:
        NNN_description.sql  (e.g. 001_initial_schema.sql)

    Already-applied migrations (recorded in schema_migrations table)
    are skipped. Migrations run in version-number order.

    Args:
        connection_manager: ConnectionManager for obtaining DB connections.
        migrations_dir: Directory containing SQL migration files.
    """

    def __init__(
        self,
        connection_manager: ConnectionManager,
        migrations_dir: Path = _MIGRATIONS_DIR,
    ) -> None:
        self._connection_manager = connection_manager
        self._migrations_dir = migrations_dir

    def run(self) -> list[int]:
        """Discover and apply all pending migrations.

        Returns:
            List of migration version numbers that were applied in this run.

        Raises:
            MigrationError: If any migration fails to apply.
        """
        migration_files = sorted(self._migrations_dir.glob("*.sql"))
        applied: list[int] = []

        # Use a single persistent connection for all migration operations.
        # This is critical for :memory: databases where each connect() call
        # creates a separate, empty database.
        conn = self._connection_manager._create_connection()
        try:
            # Bootstrap: ensure the migrations tracking table exists.
            conn.execute("BEGIN")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version     INTEGER NOT NULL PRIMARY KEY,
                    name        TEXT    NOT NULL,
                    applied_at  TEXT    NOT NULL
                )
                """
            )
            conn.execute("COMMIT")

            rows = conn.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
            already_applied: set[int] = {row[0] for row in rows}

            for migration_file in migration_files:
                version = self._extract_version(migration_file.name)
                if version is None:
                    logger.warning(
                        "Skipping non-versioned migration file",
                        extra={"context": {"file": migration_file.name}},
                    )
                    continue

                if version in already_applied:
                    logger.debug(
                        "Migration already applied, skipping",
                        extra={"context": {"version": version, "file": migration_file.name}},
                    )
                    continue

                logger.info(
                    "Applying migration",
                    extra={"context": {"version": version, "file": migration_file.name}},
                )

                sql = migration_file.read_text(encoding="utf-8")
                try:
                    # executescript() issues an implicit COMMIT before running.
                    # We rely on it to apply the SQL, then record the version.
                    conn.executescript(sql)

                    # After executescript's implicit commit, open a new transaction
                    # to record the migration as applied.
                    conn.execute("BEGIN")
                    conn.execute(
                        """
                        INSERT INTO schema_migrations (version, name, applied_at)
                        VALUES (?, ?, ?)
                        """,
                        (
                            version,
                            migration_file.stem,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                    conn.execute("COMMIT")
                except Exception as exc:
                    try:
                        conn.execute("ROLLBACK")
                    except Exception:
                        pass
                    raise MigrationError(migration_file.name, exc) from exc

                applied.append(version)
                logger.info(
                    "Migration applied successfully",
                    extra={"context": {"version": version}},
                )
        finally:
            if self._connection_manager._raw_path != ":memory:":
                conn.close()

        return applied

    @staticmethod
    def _extract_version(filename: str) -> int | None:
        """Extract the integer version number from a migration filename.

        Args:
            filename: File name like '001_initial_schema.sql'.

        Returns:
            Integer version number, or None if not parseable.
        """
        try:
            prefix = filename.split("_")[0]
            return int(prefix)
        except (ValueError, IndexError):
            return None
