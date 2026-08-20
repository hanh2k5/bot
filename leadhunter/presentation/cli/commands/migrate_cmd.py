"""CLI migrate command — runs pending database migrations (REQ-033)."""

from __future__ import annotations

import sys
import click

from leadhunter.domain.exceptions import MigrationError, LeadHunterError
from leadhunter.presentation.cli.formatters.json_formatter import format_json
from leadhunter.presentation.cli.formatters.table_formatter import format_table


@click.command()
@click.option("--format", "output_format",
              type=click.Choice(["table", "json"], case_sensitive=False),
              default="table", help="Output format")
@click.pass_context
def migrate_cmd(ctx: click.Context, output_format: str) -> None:
    """Run pending database schema migrations."""
    config = ctx.obj["config"]

    try:
        from leadhunter.infrastructure.persistence.connection_manager import ConnectionManager
        from leadhunter.infrastructure.persistence.migrations.migration_runner import MigrationRunner

        cm = ConnectionManager(config.database.path)
        runner = MigrationRunner(cm)
        applied = runner.run()
    except MigrationError as exc:
        click.echo(f"Migration Error [{exc.error_code}]: {exc.message}", err=True)
        sys.exit(1)
    except LeadHunterError as exc:
        click.echo(f"Error [{exc.error_code}]: {exc.message}", err=True)
        sys.exit(1)

    if not applied:
        click.echo("Database is up to date. No migrations needed.")
        return

    data = [{"version": v, "status": "applied"} for v in applied]

    if output_format == "json":
        click.echo(format_json({"applied_migrations": data}))
    else:
        click.echo(f"\nApplied {len(applied)} migration(s):")
        click.echo(format_table(data))
