"""Table formatter for CLI output (REQ-067)."""

from __future__ import annotations

from typing import Any


def format_table(
    records: list[dict[str, Any]],
    columns: list[str] | None = None,
    max_col_width: int = 40,
) -> str:
    """Format a list of records as a plain-text aligned table.

    Args:
        records: List of dictionaries to display.
        columns: Column names to include (in order). If None, uses all keys.
        max_col_width: Maximum width for any column value.

    Returns:
        Formatted table string.
    """
    if not records:
        return "(no records)"

    cols = columns if columns else list(records[0].keys())

    # Truncate long values
    def trunc(val: Any) -> str:
        s = str(val) if val is not None else ""
        return s[:max_col_width] + "…" if len(s) > max_col_width else s

    # Compute column widths
    widths: dict[str, int] = {col: len(col) for col in cols}
    for record in records:
        for col in cols:
            widths[col] = max(widths[col], len(trunc(record.get(col, ""))))

    # Build header
    header = " | ".join(col.ljust(widths[col]) for col in cols)
    separator = "-+-".join("-" * widths[col] for col in cols)

    rows = [header, separator]
    for record in records:
        row = " | ".join(trunc(record.get(col, "")).ljust(widths[col]) for col in cols)
        rows.append(row)

    return "\n".join(rows)
