"""SQLite connection manager — Infrastructure layer.

Configures WAL mode, foreign key enforcement, and provides a
thread-safe connection context manager (REQ-034).

Security: Database file path is configured via constructor injection,
never derived from user input. All queries use parameterized statements.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from leadhunter.domain.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages SQLite connections with WAL mode and FK enforcement (REQ-034).

    Args:
        db_path: Absolute or relative path to the SQLite database file.
    """

    def __init__(self, db_path: str) -> None:
        """Initialise the connection manager.

        Args:
            db_path: Path to the SQLite .db file. Parent directories are
                created automatically on first use.
        """
        if db_path == ":memory:":
            self._db_path = None
            self._raw_path = db_path
        else:
            # 🔒 KHÓA CHẾT ĐƯỜNG DẪN TUYỆT ĐỐI VÀO THƯ MỤC data/
            # Path(__file__) trỏ đến connection_manager.py -> lùi 3 cấp (.parents[3]) là ra thư mục gốc dự án
            project_root = Path(__file__).resolve().parents[3]
            db_name = Path(db_path).name  # Bóc lấy đúng cái tên file (leadhunter.db)

            self._db_path = project_root / "data" / db_name
            self._raw_path = str(self._db_path)

        self._memory_conn: sqlite3.Connection | None = None

    @property
    def db_path(self) -> Path:
        """Return the configured database file path."""
        return self._db_path or Path(":memory:")

    def _create_connection(self) -> sqlite3.Connection:
        """Open and configure a new SQLite connection.

        Returns:
            Configured sqlite3.Connection instance.

        Raises:
            DatabaseError: If the connection cannot be established.
        """
        if self._raw_path == ":memory:":
            if self._memory_conn is not None:
                return self._memory_conn

        try:
            if self._db_path:
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                self._raw_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                isolation_level=None,  # We manage transactions manually
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            # REQ-034: Enable WAL journal mode for concurrent reads/writes
            if self._raw_path != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL")
            # REQ-034: Enforce foreign key constraints
            conn.execute("PRAGMA foreign_keys = ON")
            # Improve performance for LIKE queries (REQ-043 keyword search)
            conn.execute("PRAGMA case_sensitive_like = OFF")

            if self._raw_path == ":memory:":
                self._memory_conn = conn
            return conn
        except sqlite3.Error as exc:
            raise DatabaseError("open_connection", exc) from exc

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that yields a configured SQLite connection.

        The connection is closed when the context exits.

        Yields:
            sqlite3.Connection configured with WAL + FK enabled.

        Raises:
            DatabaseError: On connection failure.
        """
        conn = self._create_connection()
        try:
            yield conn
        finally:
            if self._raw_path != ":memory:":
                conn.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager that yields a connection within an explicit transaction.

        Commits on successful exit; rolls back on any exception (REQ-032).

        Yields:
            sqlite3.Connection with an active BEGIN transaction.

        Raises:
            DatabaseError: On commit/rollback failure or nested errors.
        """
        conn = self._create_connection()
        try:
            conn.execute("BEGIN")
            yield conn
            conn.execute("COMMIT")
        except sqlite3.Error as exc:
            conn.execute("ROLLBACK")
            raise DatabaseError("transaction", exc) from exc
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        finally:
            if self._raw_path != ":memory:":
                conn.close()
