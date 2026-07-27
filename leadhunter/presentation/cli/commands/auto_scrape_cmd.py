"""CLI auto-scrape command — runs daily automated job (REQ-064)."""

from __future__ import annotations

import sys
import click

from leadhunter.application.use_cases.auto_run_use_case import AutoRunUseCase
from leadhunter.domain.exceptions import LeadHunterError
from leadhunter.presentation.cli.formatters.json_formatter import format_json
from leadhunter.presentation.cli.formatters.table_formatter import format_table


@click.command()
@click.option("--keyword", "-k", "keywords", multiple=True, required=True,
              help="Keywords to scrape (e.g. 'spa', 'quan cafe'). Can specify multiple.")
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table", help="Output format"
)
@click.pass_context
def auto_scrape_cmd(ctx: click.Context, keywords: list[str], output_format: str) -> None:
    """Run daily automated scraper with smart filters (HCM, No Viettel, No Web)."""
    config = ctx.obj["config"]

    try:
        from leadhunter.presentation.cli.factory import make_repository
        from leadhunter.infrastructure.adapters.google_maps_scraper import GoogleMapsScraper
        from leadhunter.infrastructure.adapters.excel_writer_adapter import ExcelWriterAdapter
        from leadhunter.application.use_cases.export_leads_to_excel import ExportLeadsToExcelUseCase

        repo = make_repository(config)

        # Load proxy config từ app config
        proxy_dict = None
        if config.proxy.server:
            proxy_dict = {"server": config.proxy.server}
            if config.proxy.username:
                proxy_dict["username"] = config.proxy.username
            if config.proxy.password:
                proxy_dict["password"] = config.proxy.password

        maps_scraper = GoogleMapsScraper(proxy=proxy_dict, api_key=config.serpapi.api_key)
        
        writer = ExcelWriterAdapter()
        export_use_case = ExportLeadsToExcelUseCase(
            repository=repo,
            excel_writer=writer,
            export_dir=config.export.output_dir,
            actor="daily_bot",
        )

        use_case = AutoRunUseCase(
            repository=repo,
            maps_scraper=maps_scraper,
            export_use_case=export_use_case
        )
        
        parsed_keywords = []
        for item in keywords:
            for kw in item.split(","):
                if kw.strip():
                    parsed_keywords.append(kw.strip())

        result = use_case.execute(parsed_keywords)

    except LeadHunterError as exc:
        click.echo(f"Error [{exc.error_code}]: {exc.message}", err=True)
        sys.exit(1)

    if output_format == "json":
        click.echo(format_json(result))
    else:
        click.echo("\n=== Daily Auto-Scrape Finished ===")
        click.echo(format_table([result]))
