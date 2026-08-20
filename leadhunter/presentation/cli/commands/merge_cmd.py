"""CLI merge-duplicate command (REQ-026)."""

from __future__ import annotations

import sys
import click

from leadhunter.application.dtos import MergeLeadInputDTO
from leadhunter.application.use_cases.merge_lead import MergeLeadUseCase
from leadhunter.domain.exceptions import LeadHunterError, LeadNotFoundError, ValidationError
from leadhunter.presentation.cli.formatters.json_formatter import format_json
from leadhunter.presentation.cli.formatters.table_formatter import format_table


@click.command()
@click.option("--duplicate-id", "duplicate_lead_id", required=True, help="UUID of the duplicate lead (to be merged)")
@click.option("--target-id", "target_lead_id", required=True, help="UUID of the canonical lead (to keep)")
@click.option("--format", "output_format",
              type=click.Choice(["table", "json"], case_sensitive=False),
              default="table", help="Output format")
@click.pass_context
def merge_cmd(
    ctx: click.Context,
    duplicate_lead_id: str,
    target_lead_id: str,
    output_format: str,
) -> None:
    """Merge a duplicate lead into its canonical original.

    Fields from the duplicate that are empty in the target will be copied over.
    """
    config = ctx.obj["config"]

    try:
        from leadhunter.presentation.cli.factory import make_repository
        repo = make_repository(config)
        use_case = MergeLeadUseCase(repository=repo)
        dto = MergeLeadInputDTO(
            duplicate_lead_id=duplicate_lead_id,
            target_lead_id=target_lead_id,
            actor=config.actor,
        )
        result = use_case.execute(dto)
    except (LeadNotFoundError, ValidationError) as exc:
        click.echo(f"Error: {exc.message}", err=True)
        sys.exit(1)
    except LeadHunterError as exc:
        click.echo(f"Error [{exc.error_code}]: {exc.message}", err=True)
        sys.exit(1)

    data = {
        "target_lead_id": result.target_lead_id,
        "fields_updated": ", ".join(result.fields_updated) if result.fields_updated else "(none)",
        "merged_at": result.merged_at,
    }

    if output_format == "json":
        click.echo(format_json(data))
    else:
        click.echo("\n=== Merge Complete ===")
        click.echo(format_table([data]))
