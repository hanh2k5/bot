"""Domain constants — status transition matrix and field definitions.

This module defines the authoritative list of allowed LeadStatus transitions.
It is the single source of truth for the state machine (REQ-041, AS-06).
No if/else transition logic should exist outside this module.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Status transition matrix (REQ-041)
# Key: current status  →  Value: set of allowed next statuses
# ---------------------------------------------------------------------------
STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "NEW": frozenset({"VALIDATED", "REJECTED", "DUPLICATE"}),
    "VALIDATED": frozenset({"CONTACTED", "REJECTED"}),
    "CONTACTED": frozenset({"QUALIFIED", "REJECTED"}),
    "QUALIFIED": frozenset({"CONVERTED", "REJECTED"}),
    # Terminal states — no outgoing transitions allowed
    "CONVERTED": frozenset(),
    "REJECTED": frozenset(),
    "DUPLICATE": frozenset(),
}

# ---------------------------------------------------------------------------
# Required columns for file import (REQ-002)
# ---------------------------------------------------------------------------
REQUIRED_IMPORT_COLUMNS: frozenset[str] = frozenset(
    {
        "company_name",
        "contact_name",
        "email",
        "phone",
        "website",
        "address",
    }
)

# ---------------------------------------------------------------------------
# Lead score bounds (REQ-051)
# ---------------------------------------------------------------------------
SCORE_MIN: int = 0
SCORE_MAX: int = 100

# ---------------------------------------------------------------------------
# Default lead status on creation (REQ-038)
# ---------------------------------------------------------------------------
DEFAULT_LEAD_STATUS: str = "NEW"

# ---------------------------------------------------------------------------
# User-Agent string for web scraping (REQ-015)
# ---------------------------------------------------------------------------
SCRAPER_USER_AGENT: str = "LeadHunterBot/1.0"

# ---------------------------------------------------------------------------
# Export file naming pattern (REQ-059)
# ---------------------------------------------------------------------------
EXPORT_FILE_PATTERN: str = "leadhunter_export_{datetime_str}.xlsx"

# ---------------------------------------------------------------------------
# Supported file encodings for CSV import (REQ-004)
# ---------------------------------------------------------------------------
SUPPORTED_CSV_ENCODINGS: tuple[str, ...] = ("utf-8", "utf-8-sig")

# ---------------------------------------------------------------------------
# Minimum export columns (REQ-057)
# ---------------------------------------------------------------------------
EXPORT_COLUMNS: tuple[str, ...] = (
    "company_name",
    "contact_name",
    "email",
    "phone",
    "website",
    "address",
    "status",
    "score",
    "source",
    "created_at",
)
