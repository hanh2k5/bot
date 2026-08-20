"""CLI scrape command (REQ-009 through REQ-016)."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from leadhunter.application.use_cases.scrape_leads_from_urls import ScrapeLeadsFromUrlsUseCase
from leadhunter.domain.exceptions import LeadHunterError
from leadhunter.domain.services.dedup_service import DeduplicationConfig
from leadhunter.presentation.cli.formatters.json_formatter import format_json
from leadhunter.presentation.cli.formatters.table_formatter import format_table


@click.command()
@click.option(
    "--urls-file", "urls_file", required=True,
    help="Path to a text file with one URL per line"
)
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table", help="Output format"
)
@click.pass_context
def scrape_cmd(ctx: click.Context, urls_file: str, output_format: str) -> None:
    """Scrape leads from a list of URLs (one URL per line in the file)."""
    config = ctx.obj["config"]

    urls_path = Path(urls_file)
    if not urls_path.exists():
        click.echo(f"Error: URLs file not found: {urls_file}", err=True)
        sys.exit(1)

    try:
        urls = [
            line.strip()
            for line in urls_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
    except OSError as exc:
        click.echo(f"Error reading URLs file: {exc}", err=True)
        sys.exit(1)

    if not urls:
        click.echo("Error: No valid URLs found in the file.", err=True)
        sys.exit(1)

    try:
        from leadhunter.presentation.cli.factory import make_repository
        from leadhunter.infrastructure.adapters.web_scraper_adapter import WebScraperAdapter

        repo = make_repository(config)
        scraper = WebScraperAdapter(
            http_timeout=config.ingestion.http_timeout_seconds,
            retry_max_attempts=config.ingestion.retry_max_attempts,
            rate_limit_delay=config.ingestion.rate_limit_delay_seconds,
            cache_ttl_hours=config.ingestion.cache_ttl_hours,
        )
        use_case = ScrapeLeadsFromUrlsUseCase(
            repository=repo,
            scraper_adapter=scraper,
            dedup_config=DeduplicationConfig(),
            max_urls=config.ingestion.max_urls_per_run,
            actor=config.actor,
        )
        result = use_case.execute(urls)
    except LeadHunterError as exc:
        click.echo(f"Error [{exc.error_code}]: {exc.message}", err=True)
        sys.exit(1)

    summary = {
        "import_batch_id": result.import_batch_id,
        "success_count": result.success_count,
        "error_count": result.error_count,
        "duplicate_count": result.duplicate_count,
        "executed_at": result.executed_at,
    }

    if output_format == "json":
        data = {**summary, "url_errors": [vars(e) for e in result.url_errors]}
        click.echo(format_json(data))
    else:
        click.echo("\n=== Scrape Summary ===")
        click.echo(format_table([summary]))
        if result.url_errors:
            click.echo(f"\n{result.error_count} URL(s) had errors:")
            errors = [
                {"URL": e.url[:60], "Code": e.error_code, "Message": e.message[:60]}
                for e in result.url_errors[:10]
            ]
            click.echo(format_table(errors))
