"""Structured JSON log formatter — Infrastructure layer (LOG-002).

Formats log records as single-line JSON objects for structured logging.
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Log formatter that emits each record as a JSON object (LOG-002).

    Output fields per log line:
      - timestamp: ISO 8601 UTC string
      - level: Log level name
      - logger_name: Logger name (dotted module path)
      - correlation_id: Request/command correlation ID (from LogRecord.correlation_id)
      - message: The formatted log message
      - context: Additional structured data dict (from LogRecord.context)
      - exc_info: Exception traceback string (if exc_info was set)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a LogRecord as a JSON string.

        Args:
            record: The LogRecord to format.

        Returns:
            Single-line JSON string.
        """
        log_data: dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger_name": record.name,
            "correlation_id": getattr(record, "correlation_id", ""),
            "message": record.getMessage(),
            "context": getattr(record, "context", {}),
        }

        if record.exc_info:
            log_data["exc_info"] = traceback.format_exception(*record.exc_info)

        # Security: never log sensitive fields (LOG-005)
        # Mask any 'password', 'token', 'api_key' keys in context
        if isinstance(log_data.get("context"), dict):
            log_data["context"] = _mask_sensitive(log_data["context"])

        return json.dumps(log_data, ensure_ascii=False, default=str)


_SENSITIVE_KEYS = frozenset(
    {"password", "token", "api_key", "secret", "authorization", "credential"}
)


def _mask_sensitive(data: dict) -> dict:
    """Recursively mask sensitive keys in a dictionary (LOG-005).

    Args:
        data: Dictionary to sanitise.

    Returns:
        Sanitised copy of the dictionary.
    """
    result = {}
    for key, value in data.items():
        if key.lower() in _SENSITIVE_KEYS:
            result[key] = "***REDACTED***"
        elif isinstance(value, dict):
            result[key] = _mask_sensitive(value)
        else:
            result[key] = value
    return result
