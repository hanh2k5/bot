"""CLI score command (REQ-049 through REQ-055)."""

from __future__ import annotations

import sys
from typing import Optional

import click

from leadhunter.application.use_cases.score_leads import ScoreLeadUseCase, ScoreLeadsBatchUseCase
from leadhunter.domain.exceptions import LeadHunterError, LeadNotFoundError
from leadhunter.presentation.cli.formatters.json_formatter import format_json
from leadhunter.presentation.cli.formatters.table_formatter import format_table


@click.command()
@click.option("--lead-id", "lead_id", default=None, help="Score a single lead by UUID")
@click.option("--all", "score_all", is_flag=True, default=False, help="Score all leads in batch")
@click.option("--batch-size", "batch_size", type=int, default=None, help="Batch size for --all mode")
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table", help="Output format"
)
@click.pass_context
def score_cmd(
    ctx: click.Context,
    lead_id: Optional[str],
    score_all: bool,
    batch_size: Optional[int],
    output_format: str,
) -> None:
    """Score one or all leads using the configured scoring rules.

    Use --lead-id to score a single lead, or --all to score all leads in batch.
    """
    if not lead_id and not score_all:
        click.echo("Error: Specify --lead-id <UUID> or --all", err=True)
        sys.exit(1)

    config = ctx.obj["config"]
    effective_batch_size = batch_size or config.scoring.batch_size

    try:
        from leadhunter.presentation.cli.factory import make_repository, make_scoring_rules
        repo = make_repository(config)
        scoring_rules = make_scoring_rules()

        if lead_id:
            use_case = ScoreLeadUseCase(repository=repo, scoring_rules=scoring_rules)
            result = use_case.execute(lead_id)
            data = {
                "lead_id": result.lead_id,
                "old_score": result.old_score,
                "new_score": result.new_score,
                "updated_at": result.updated_at,
            }
            if output_format == "json":
                click.echo(format_json(data))
            else:
                click.echo("\n=== Score Result ===")
                click.echo(format_table([data]))
        else:
            batch_use_case = ScoreLeadsBatchUseCase(
                repository=repo,
                scoring_rules=scoring_rules,
                batch_size=effective_batch_size,
            )
            result_batch = batch_use_case.execute()
            data = {
                "processed_count": result_batch.processed_count,
                "updated_count": result_batch.updated_count,
                "elapsed_ms": round(result_batch.elapsed_ms, 2),
            }
            if output_format == "json":
                click.echo(format_json(data))
            else:
                click.echo("\n=== Batch Score Summary ===")
                click.echo(format_table([data]))

    except LeadNotFoundError as exc:
        click.echo(f"Error: {exc.message}", err=True)
        sys.exit(1)
    except LeadHunterError as exc:
        click.echo(f"Error [{exc.error_code}]: {exc.message}", err=True)
        sys.exit(1)
