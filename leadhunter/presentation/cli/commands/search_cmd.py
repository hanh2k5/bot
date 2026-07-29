"""CLI search command (REQ-043 through REQ-048)."""

from __future__ import annotations

import sys
from typing import Optional

import click

from leadhunter.application.dtos import SearchParamsDTO
from leadhunter.application.use_cases.search_leads import SearchLeadsUseCase
from leadhunter.domain.exceptions import LeadHunterError, ValidationError
from leadhunter.presentation.cli.formatters.json_formatter import format_json
from leadhunter.presentation.cli.formatters.table_formatter import format_table

_DISPLAY_COLUMNS = [
    "id", "company_name", "contact_name", "email", "phone", "status", "score", "source"
]


@click.command()
@click.option("--status", default=None, help="Filter by status (NEW, VALIDATED, etc.)")
@click.option("--score-min", "score_min", type=int, default=None, help="Minimum score (0-100)")
@click.option("--score-max", "score_max", type=int, default=None, help="Maximum score (0-100)")
@click.option("--source", default=None, help="Filter by source (excel, web)")
@click.option("--keyword", "-k", default=None, help="Keyword search on company, contact, email")
@click.option("--from", "created_from", default=None, help="Created from date (ISO 8601)")
@click.option("--to", "created_to", default=None, help="Created to date (ISO 8601)")
@click.option("--include-duplicates", is_flag=True, default=False, help="Include DUPLICATE status leads")
@click.option("--page", type=int, default=1, help="Page number (default: 1)")
@click.option("--page-size", "page_size", type=int, default=20, help="Records per page (default: 20)")
@click.option("--sort-by", "sort_by", default="created_at",
              type=click.Choice(["created_at", "score", "company_name", "updated_at"]),
              help="Sort field")
@click.option("--order", "sort_order", default="desc",
              type=click.Choice(["asc", "desc"]), help="Sort order")
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table", help="Output format"
)
@click.pass_context
def search_cmd(
    ctx: click.Context,
    status: Optional[str],
    score_min: Optional[int],
    score_max: Optional[int],
    source: Optional[str],
    keyword: Optional[str],
    created_from: Optional[str],
    created_to: Optional[str],
    include_duplicates: bool,
    page: int,
    page_size: int,
    sort_by: str,
    sort_order: str,
    output_format: str,
) -> None:
    """Search and filter leads with pagination."""
    config = ctx.obj["config"]

    try:
        from leadhunter.presentation.cli.factory import make_repository
        repo = make_repository(config)
        use_case = SearchLeadsUseCase(
            repository=repo,
            max_page_size=config.query.max_page_size,
            default_page_size=config.query.default_page_size,
        )
        params = SearchParamsDTO(
            status=status,
            score_min=score_min,
            score_max=score_max,
            source=source,
            keyword=keyword,
            created_from=created_from,
            created_to=created_to,
            include_duplicates=include_duplicates,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        result = use_case.execute(params)
    except ValidationError as exc:
        click.echo(f"Validation Error: {exc.message}", err=True)
        sys.exit(1)
    except LeadHunterError as exc:
        click.echo(f"Error [{exc.error_code}]: {exc.message}", err=True)
        sys.exit(1)

    if output_format == "json":
        data = {
            "leads": [vars(lead) for lead in result.leads],
            "total_count": result.total_count,
            "page": result.page,
            "page_size": result.page_size,
        }
        click.echo(format_json(data))
    else:
        total_pages = (result.total_count + result.page_size - 1) // result.page_size
        click.echo(
            f"\nFound {result.total_count} lead(s) — "
            f"Page {result.page}/{max(1, total_pages)}\n"
        )
        records = [
            {col: getattr(lead, col, "") for col in _DISPLAY_COLUMNS}
            for lead in result.leads
        ]
        click.echo(format_table(records, columns=_DISPLAY_COLUMNS))
