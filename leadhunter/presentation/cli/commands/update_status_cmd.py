"""CLI update-status command (REQ-036 through REQ-042)."""

from __future__ import annotations

import sys
from typing import Optional

import click

from leadhunter.application.dtos import UpdateStatusInputDTO
from leadhunter.application.use_cases.update_lead_status import UpdateLeadStatusUseCase
from leadhunter.domain.exceptions import (
    InvalidStatusTransitionError,
    LeadHunterError,
    LeadNotFoundError,
    ValidationError,
)
from leadhunter.presentation.cli.formatters.json_formatter import format_json
from leadhunter.presentation.cli.formatters.table_formatter import format_table


@click.command()
@click.option("--lead-id", "lead_id", required=True, help="UUID of the lead to update")
@click.option(
    "--status",
    required=True,
    type=click.Choice(
        ["VALIDATED", "CONTACTED", "QUALIFIED", "CONVERTED", "REJECTED", "DUPLICATE"],
        case_sensitive=False,
    ),
    help="New status for the lead",
)
@click.option("--reason", default=None, help="Optional reason for status change")
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table", help="Output format"
)
@click.pass_context
def update_status_cmd(
    ctx: click.Context,
    lead_id: str,
    status: str,
    reason: Optional[str],
    output_format: str,
) -> None:
    """Update the lifecycle status of a lead.

    Valid transitions:
      NEW → VALIDATED, REJECTED, DUPLICATE
      VALIDATED → CONTACTED, REJECTED
      CONTACTED → QUALIFIED, REJECTED
      QUALIFIED → CONVERTED, REJECTED
      CONVERTED, REJECTED, DUPLICATE → (terminal, no further transitions)
    """
    config = ctx.obj["config"]

    try:
        from leadhunter.presentation.cli.factory import make_repository
        repo = make_repository(config)
        use_case = UpdateLeadStatusUseCase(repository=repo)
        dto = UpdateStatusInputDTO(
            lead_id=lead_id,
            new_status=status.upper(),
            actor=config.actor,
            reason=reason,
        )
        result = use_case.execute(dto)
    except LeadNotFoundError as exc:
        click.echo(f"Error: {exc.message}", err=True)
        sys.exit(1)
    except InvalidStatusTransitionError as exc:
        click.echo(f"Error: {exc.message}", err=True)
        sys.exit(1)
    except (ValidationError, LeadHunterError) as exc:
        click.echo(f"Error [{exc.error_code}]: {exc.message}", err=True)
        sys.exit(1)

    data = {
        "lead_id": result.lead_id,
        "old_status": result.old_status,
        "new_status": result.new_status,
        "changed_at": result.changed_at,
    }

    if output_format == "json":
        click.echo(format_json(data))
    else:
        click.echo("\n=== Status Updated ===")
        click.echo(format_table([data]))
