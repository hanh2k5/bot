"""LeadHunter CLI — main entrypoint (REQ-063 through REQ-068).

Provides the Click command group with global error handling (NFR-004, REQ-065, REQ-066)
and correlation ID injection (NFR-014).
"""

from __future__ import annotations

import io
import logging
import sys
import traceback
import uuid

import click


def _configure_utf8_streams() -> None:
    """Ensure sys.stdout and sys.stderr use UTF-8 with replacement for invalid chars on Windows."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        elif stream and hasattr(stream, "buffer"):
            try:
                setattr(sys, stream_name, io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace"))
            except Exception:
                pass


_configure_utf8_streams()

from leadhunter import __version__
from leadhunter.infrastructure.config.config_loader import load_config
from leadhunter.infrastructure.logging.logging_config import (
    CorrelationIdFilter,
    configure_logging,
)
from leadhunter.domain.services.auth_service import check_or_prompt_activation

logger = logging.getLogger(__name__)


def _setup(ctx: click.Context, verbose: bool) -> None:
    """Initialize logging and load config into Click context.

    Args:
        ctx: Click context object.
        verbose: Whether to enable verbose console output.
    """
    # Free open access - no license prompt

    config = load_config()
    configure_logging(
        log_level=config.logging.level,
        log_file_path=config.logging.file_path,
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
        verbose=verbose,
    )
    # Inject correlation_id into all log records for this invocation (NFR-014)
    correlation_id = str(uuid.uuid4())
    corr_filter = CorrelationIdFilter(correlation_id)
    logging.getLogger().addFilter(corr_filter)

    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["correlation_id"] = correlation_id
    ctx.obj["verbose"] = verbose


@click.group()
@click.version_option(version=__version__, prog_name="leadhunter")
@click.option("--verbose", "-v", is_flag=True, default=False, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """LeadHunter — Lead collection, management, and scoring system.

    Manage your leads from ingestion to export with a clean CLI interface.
    Use --help on any subcommand for detailed usage.
    """
    _setup(ctx, verbose)


from leadhunter.presentation.cli.commands.scrape_cmd import scrape_cmd
from leadhunter.presentation.cli.commands.update_status_cmd import update_status_cmd
from leadhunter.presentation.cli.commands.export_cmd import export_cmd
from leadhunter.presentation.cli.commands.merge_cmd import merge_cmd
from leadhunter.presentation.cli.commands.auto_scrape_cmd import auto_scrape_cmd
from leadhunter.presentation.cli.commands.reset_db_cmd import reset_db_cmd
from leadhunter.presentation.cli.commands.rollback_cmd import rollback_cmd
from leadhunter.presentation.cli.commands.quet_cmd import quet_cmd
from leadhunter.presentation.cli.commands.nap_cmd import nap_cmd

cli.add_command(scrape_cmd, name="scrape")
cli.add_command(update_status_cmd, name="update-status")
cli.add_command(export_cmd, name="export")
cli.add_command(merge_cmd, name="merge-duplicate")
cli.add_command(auto_scrape_cmd, name="auto-scrape")
cli.add_command(reset_db_cmd, name="reset-db")
cli.add_command(rollback_cmd, name="rollback")
cli.add_command(quet_cmd, name="quet")
cli.add_command(nap_cmd, name="nap")


def main() -> None:
    """CLI entry point with global exception handler (NFR-004, REQ-065, REQ-066).

    Exit codes:
      0 — Success
      1 — Handled business error (e.g. invalid file, validation error)
      2 — Unexpected system error (logged with full traceback)
    """
    try:
        cli(standalone_mode=False)
    except click.ClickException as exc:
        exc.show()
        sys.exit(1)
    except click.Abort:
        click.echo("\nAborted.", err=True)
        sys.exit(1)
    except SystemExit as exc:
        sys.exit(exc.code)
    except Exception as exc:
        logger.error(
            "Unexpected system error",
            exc_info=exc,
            extra={"context": {"error": str(exc)}},
        )
        print(f"Error: {exc}\n{traceback.format_exc()}", file=sys.stderr)
        sys.exit(2)

def cao_main() -> None:
    """Standalone entry point for the 'cao' shortcut."""
    import sys
    # Insert 'auto-scrape' as the subcommand so main() routes it correctly
    sys.argv.insert(1, "auto-scrape")
    main()

def reset_main() -> None:
    """Standalone entry point for the 'reset' shortcut."""
    import sys
    sys.argv.insert(1, "reset-db")
    main()

def xuat_main() -> None:
    """Standalone entry point for the 'xuat' shortcut."""
    import sys
    sys.argv.insert(1, "export")
    main()

def huy_main() -> None:
    """Standalone entry point for the 'huy' shortcut."""
    import sys
    sys.argv.insert(1, "rollback")
    main()

def quet_main() -> None:
    """Standalone entry point for the 'gop' shortcut."""
    import sys
    sys.argv.insert(1, "quet")
    main()

def nap_main() -> None:
    """Standalone entry point for the 'nap' shortcut."""
    import sys
    sys.argv.insert(1, "nap")
    main()



def app_main() -> None:
    """Standalone entry point for launching the GUI App ('run' shortcut)."""
    import os
    import sys
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))
    from gui_app import main as gui_run
    gui_run()


if __name__ == "__main__":
    main()
