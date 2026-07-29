"""CLI export command (REQ-056 through REQ-062)."""

from __future__ import annotations

import sys
from typing import Optional

import click

from leadhunter.application.dtos import ExportParamsDTO
from leadhunter.application.use_cases.export_leads_to_excel import ExportLeadsToExcelUseCase
from leadhunter.domain.exceptions import LeadHunterError, NoDataToExportError
from leadhunter.presentation.cli.formatters.json_formatter import format_json
from leadhunter.presentation.cli.formatters.table_formatter import format_table


@click.command()
@click.option("--output", "-o", "output_path", default=None, help="Output file path (default: auto-named)")
@click.option("--status", default=None, help="Filter by status")
@click.option("--score-min", "score_min", type=int, default=None, help="Minimum score")
@click.option("--score-max", "score_max", type=int, default=None, help="Maximum score")
@click.option("--source", default=None, help="Filter by source")
@click.option("--keyword", "-k", default=None, help="Keyword filter")
@click.option("--from", "created_from", default=None, help="Created from date (ISO 8601)")
@click.option("--to", "created_to", default=None, help="Created to date (ISO 8601)")
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table", help="Output format"
)
@click.pass_context
def export_cmd(
    ctx: click.Context,
    output_path: Optional[str],
    status: Optional[str],
    score_min: Optional[int],
    score_max: Optional[int],
    source: Optional[str],
    keyword: Optional[str],
    created_from: Optional[str],
    created_to: Optional[str],
    output_format: str,
) -> None:
    """Export leads to an Excel (.xlsx) file."""
    config = ctx.obj["config"]

    try:
        from leadhunter.presentation.cli.factory import make_repository
        from leadhunter.infrastructure.adapters.excel_writer_adapter import ExcelWriterAdapter

        repo = make_repository(config)
        writer = ExcelWriterAdapter()
        use_case = ExportLeadsToExcelUseCase(
            repository=repo,
            excel_writer=writer,
            export_dir=config.export.output_dir,
            actor=config.actor,
        )
        params = ExportParamsDTO(
            output_path=output_path,
            actor=config.actor,
            status=status,
            score_min=score_min,
            score_max=score_max,
            source=source,
            keyword=keyword,
            created_from=created_from,
            created_to=created_to,
        )
        result = use_case.execute(params)
    except NoDataToExportError as exc:
        click.echo(f"Notice: {exc.message}", err=False)
        sys.exit(0)
    except LeadHunterError as exc:
        click.echo(f"Error [{exc.error_code}]: {exc.message}", err=True)
        sys.exit(1)

    data = {
        "output_file": result.output_file_path,
        "record_count": result.record_count,
        "executed_at": result.executed_at,
    }

    if output_format == "json":
        click.echo(format_json(data))
    else:
        import os
        file_name = os.path.basename(result.output_file_path)
        dir_name = os.path.dirname(result.output_file_path)
        time_str = result.executed_at[:19].replace("T", " ") if result.executed_at else "N/A"

        click.echo()
        click.secho("📦 ĐÓNG GÓI DỮ LIỆU THÀNH CÔNG!", fg="green", bold=True)
        click.secho("───────────────────────────────────────────────────", fg="cyan")
        
        click.secho(" 🎯 Số lượng Lead : ", fg="yellow", nl=False)
        click.secho(f"{result.record_count} số mới nhất", fg="white", bold=True)
        
        click.secho(" 📁 Tên file Excel: ", fg="yellow", nl=False)
        click.secho(f"{file_name}", fg="white", bold=True)
        
        click.secho(" 📂 Thư mục lưu   : ", fg="yellow", nl=False)
        click.secho(f"{dir_name}", fg="white")
        
        click.secho(" ⏰ Thời gian xuất: ", fg="yellow", nl=False)
        click.secho(f"{time_str}", fg="white")
        
        click.secho("───────────────────────────────────────────────────", fg="cyan")
        click.secho("✅ File đã sẵn sàng! Mở lên và sale ngay thôi sếp ơi!", fg="green", bold=True)
