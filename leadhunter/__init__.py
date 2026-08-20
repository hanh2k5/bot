"""LeadHunter – Lead collection, management, and scoring system.

Phase 1: CLI-based single-user application built on Clean Architecture.
"""

import sys


def _setup_utf8_encoding() -> None:
    """Ensure sys.stdout and sys.stderr use UTF-8 with fallback replacement on Windows."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_setup_utf8_encoding()

__version__ = "1.0.0"
