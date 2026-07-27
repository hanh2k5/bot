"""Centralized logging configuration — Infrastructure layer (LOG-001 through LOG-007).

Called ONCE at application startup. No other module should call
logging.basicConfig() or configure handlers independently (LOG-001).
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import Optional

from leadhunter.infrastructure.logging.json_formatter import JsonFormatter


def configure_logging(
    log_level: str = "INFO",
    log_file_path: str = "logs/leadhunter.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB (LOG-004)
    backup_count: int = 10,              # Keep 10 rotated files (LOG-004)
    verbose: bool = False,
) -> None:
    """Configure the root logger with structured JSON output.

    Sets up:
      - File handler: rotating, JSON format, captures DEBUG+ (LOG-007a).
      - Console handler: JSON format, captures WARNING+ by default,
        or INFO+ if verbose=True (LOG-007b).

    This function must be called exactly once at startup (LOG-001).

    Args:
        log_level: Minimum log level for the file handler (default 'INFO').
        log_file_path: Path to the rotating log file.
        max_bytes: Maximum size per log file in bytes before rotation (LOG-004).
        backup_count: Number of rotated log files to retain (LOG-004).
        verbose: If True, console also shows INFO-level messages.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything; handlers filter

    # Avoid adding duplicate handlers if called multiple times
    if root_logger.handlers:
        return

    formatter = JsonFormatter()

    # ----- File handler (LOG-007a: full DEBUG+ log for operations/debugging) -----
    log_path = Path(log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        str(log_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_level = getattr(logging, log_level.upper(), logging.INFO)
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # ----- Console handler (LOG-007b: WARNING+ for users; INFO+ in verbose mode) -----
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO if verbose else logging.WARNING)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


class CorrelationIdFilter(logging.Filter):
    """Logging filter that injects a correlation_id into every LogRecord (NFR-014).

    Attach this filter to handlers or the root logger so that all log
    records within a single CLI command invocation share the same ID.

    Args:
        correlation_id: The UUID string to inject.
    """

    def __init__(self, correlation_id: str) -> None:
        super().__init__()
        self._correlation_id = correlation_id

    def filter(self, record: logging.LogRecord) -> bool:
        """Inject correlation_id into the record.

        Args:
            record: The log record being processed.

        Returns:
            Always True (this filter never drops records).
        """
        record.correlation_id = self._correlation_id  # type: ignore[attr-defined]
        return True
