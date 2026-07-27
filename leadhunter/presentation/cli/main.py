"""LeadHunter CLI — main entrypoint (REQ-063 through REQ-068).

Provides the Click command group with global error handling (NFR-004, REQ-065, REQ-066)
and correlation ID injection (NFR-014).
"""

from __future__ import annotations

import logging
import sys
import traceback
import uuid

import click

from leadhunter import __version__
from leadhunter.infrastructure.config.config_loader import load_config
from leadhunter.infrastructure.logging.logging_config import (
    CorrelationIdFilter,
    configure_logging,
)

logger = logging.getLogger(__name__)


def _setup(ctx: click.Context, verbose: bool) -> None:
    """Initialize logging and load config into Click context.

    Args:
        ctx: Click context object.
        verbose: Whether to enable verbose console output.
    """
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


# Import and attach all subcommands
from leadhunter.presentation.cli.commands.import_cmd import import_cmd
from leadhunter.presentation.cli.commands.scrape_cmd import scrape_cmd
from leadhunter.presentation.cli.commands.search_cmd import search_cmd
from leadhunter.presentation.cli.commands.update_status_cmd import update_status_cmd
from leadhunter.presentation.cli.commands.score_cmd import score_cmd
from leadhunter.presentation.cli.commands.export_cmd import export_cmd
from leadhunter.presentation.cli.commands.merge_cmd import merge_cmd
from leadhunter.presentation.cli.commands.migrate_cmd import migrate_cmd
from leadhunter.presentation.cli.commands.auto_scrape_cmd import auto_scrape_cmd
from leadhunter.presentation.cli.commands.reset_db_cmd import reset_db_cmd

cli.add_command(import_cmd, name="import")
cli.add_command(scrape_cmd, name="scrape")
cli.add_command(search_cmd, name="search")
cli.add_command(update_status_cmd, name="update-status")
cli.add_command(score_cmd, name="score")
cli.add_command(export_cmd, name="export")
cli.add_command(merge_cmd, name="merge-duplicate")
cli.add_command(migrate_cmd, name="migrate")
cli.add_command(auto_scrape_cmd, name="auto-scrape")
cli.add_command(reset_db_cmd, name="reset-db")


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
        # REQ-066: No raw Python traceback on stdout
        click.echo(
            f"\nUnexpected error: {exc}\n"
            "Please check the log file for details.",
            err=True,
        )
        # LOG-006: Log full traceback at ERROR/CRITICAL level
        logger.critical(
            "Unhandled exception in CLI",
            exc_info=True,
            extra={"context": {"error_type": type(exc).__name__}},
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
