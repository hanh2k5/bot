"""JSON formatter for CLI output (REQ-067)."""

from __future__ import annotations

import json
from typing import Any


def format_json(data: Any, indent: int = 2) -> str:
    """Format data as pretty-printed JSON.

    Args:
        data: Any JSON-serialisable object.
        indent: Indentation level (default 2).

    Returns:
        Pretty-printed JSON string.
    """
    return json.dumps(data, indent=indent, ensure_ascii=False, default=str)
