"""CLI import command (REQ-001 through REQ-008)."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from leadhunter.application.use_cases.import_leads_from_file import ImportLeadsFromFileUseCase
from leadhunter.domain.exceptions import (
    FileTooLargeError,
    MissingRequiredColumnError,
    LeadHunterError,
)
from leadhunter.domain.services.dedup_service import DeduplicationConfig
from leadhunter.presentation.cli.formatters.json_formatter import format_json
from leadhunter.presentation.cli.formatters.table_formatter import format_table


@click.command()
@click.option("--file", "-f", required=True, help="Path to .xlsx or .csv file to import")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format (table or json)",
)
@click.pass_context
def import_cmd(ctx: click.Context, file: str, output_format: str) -> None:
    """Import leads from an Excel (.xlsx) or CSV file.

    The file must have columns: company_name, contact_name, email, phone, website, address.
    """
    config = ctx.obj["config"]
    actor = config.actor

    # Determine adapter based on file extension
    file_path = Path(file)
    ext = file_path.suffix.lower()

    try:
        from leadhunter.presentation.cli.factory import make_repository
        from leadhunter.infrastructure.adapters.excel_reader_adapter import ExcelReaderAdapter
        from leadhunter.infrastructure.adapters.csv_reader_adapter import CsvReaderAdapter

        repo = make_repository(config)

        if ext in (".xlsx",):
            adapter = ExcelReaderAdapter()
        elif ext in (".csv",):
            adapter = CsvReaderAdapter()
        else:
            click.echo(f"Error: Unsupported file type '{ext}'. Use .xlsx or .csv", err=True)
            sys.exit(1)

        dedup_config = DeduplicationConfig()
        use_case = ImportLeadsFromFileUseCase(
            repository=repo,
            adapter=adapter,
            dedup_config=dedup_config,
            max_file_size_mb=config.ingestion.max_file_size_mb,
            actor=actor,
        )
        result = use_case.execute(str(file_path.resolve()))

    except (FileTooLargeError, MissingRequiredColumnError) as exc:
        click.echo(f"Error: {exc.message}", err=True)
        sys.exit(1)
    except LeadHunterError as exc:
        click.echo(f"Error [{exc.error_code}]: {exc.message}", err=True)
        sys.exit(1)

    # Display results (REQ-067)
    summary = {
        "import_batch_id": result.import_batch_id,
        "source_file": result.source_file_name,
        "success_count": result.success_count,
        "error_count": result.error_count,
        "duplicate_count": result.duplicate_count,
        "executed_at": result.executed_at,
    }

    if output_format == "json":
        data = {
            **summary,
            "row_errors": [
                {
                    "row": e.row_index,
                    "field": e.field,
                    "code": e.error_code,
                    "message": e.message,
                }
                for e in result.row_errors
            ],
        }
        click.echo(format_json(data))
    else:
        click.echo("\n=== Import Summary ===")
        click.echo(format_table([summary]))
        if result.row_errors:
            click.echo(f"\n{result.error_count} row(s) had errors:")
            errors = [
                {
                    "Row": e.row_index,
                    "Field": e.field,
                    "Code": e.error_code,
                    "Message": e.message,
                }
                for e in result.row_errors[:20]  # Show first 20
            ]
            click.echo(format_table(errors))
            if len(result.row_errors) > 20:
                click.echo(f"  ... and {len(result.row_errors) - 20} more errors. See log for full details.")

    # Exit code: 0 if any success, 1 if complete failure
    if result.success_count == 0 and result.error_count > 0:
        sys.exit(1)
