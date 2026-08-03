"""CLI auto-scrape command — runs daily automated job (REQ-064)."""

from __future__ import annotations

import sys
import click

from leadhunter.application.use_cases.auto_run_use_case import AutoRunUseCase
from leadhunter.domain.exceptions import LeadHunterError
from leadhunter.presentation.cli.formatters.json_formatter import format_json
from leadhunter.presentation.cli.formatters.table_formatter import format_table


@click.command()
@click.argument("keywords", nargs=-1, required=True)
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table", help="Output format"
)
@click.option(
    "--target", "-t",
    type=int, default=80, help="Tổng số lượng Lead mục tiêu cần cào (Mặc định: 80)"
)
@click.option(
    "--viettel/--no-viettel", "allow_viettel",
    default=False, help="Cho phép lấy cả số Viettel (Mặc định: --no-viettel)"
)
@click.option(
    "--web/--no-web", "allow_web",
    default=False, help="Cho phép lấy cả công ty đã có Website (Mặc định: --no-web)"
)
@click.pass_context
def auto_scrape_cmd(
    ctx: click.Context,
    keywords: tuple[str, ...],
    output_format: str,
    target: int,
    allow_viettel: bool,
    allow_web: bool,
) -> None:
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
        
        parsed_keywords = [k.strip() for k_str in keywords for k in k_str.split(",") if k.strip()]
        if not parsed_keywords:
            click.secho("❌ Không có từ khóa hợp lệ.", fg="red")
            sys.exit(1)

        result = use_case.execute(
            parsed_keywords,
            target=target,
            allow_viettel=allow_viettel,
            allow_web=allow_web,
        )
        click.secho(f"\n✅ Hoàn thành Auto-scrape! Kết quả đã được lưu.", fg="green")

    except LeadHunterError as exc:
        if exc.error_code == "GOOGLE_MAPS_BLOCKED":
            click.secho(f"\\n🚨 [LỖI NGHIÊM TRỌNG]: {exc.message}", fg="red", bold=True)
            click.secho("=> Hướng giải quyết: Hãy thử đổi mạng Wi-Fi sang 4G, hoặc bật/tắt chế độ máy bay, hoặc dùng VPN.", fg="yellow")
        else:
            click.echo(f"Error [{exc.error_code}]: {exc.message}", err=True)
        sys.exit(1)

    if output_format == "json":
        click.echo(format_json(result))
    else:
        import os
        export_file = result.get("export_file", "")
        file_name = os.path.basename(export_file) if export_file else "Không có file"
        dir_name = os.path.dirname(export_file) if export_file else ""
        
        # Thống kê rác
        web = result.get('skipped_has_website', 0)
        viettel = result.get('skipped_viettel', 0)
        not_hcm = result.get('skipped_not_hcm', 0)
        dup = result.get('skipped_duplicate', 0)

        click.echo()
        click.secho("🎉 CHIẾN DỊCH ĐI SĂN HOÀN TẤT!", fg="green", bold=True)
        click.secho("───────────────────────────────────────────────────", fg="cyan")
        
        click.secho(" 🎯 Thu hoạch    : ", fg="yellow", nl=False)
        click.secho(f"{result.get('added_count', 0)} số mới", fg="white", bold=True)
        
        click.secho(" 🗑️ Đã vứt sọt rác: ", fg="red", nl=False)
        trash_items = []
        if web > 0:
            trash_items.append(f"{web} web")
        if viettel > 0:
            trash_items.append(f"{viettel} viettel/bàn")
        if not_hcm > 0:
            trash_items.append(f"{not_hcm} ngoại thành")
        if dup > 0:
            trash_items.append(f"{dup} trùng")
        
        trash_str = " | ".join(trash_items) if trash_items else "Sạch bong 100%"
        click.secho(trash_str, fg="white")
        
        click.secho(" 📁 Tên file     : ", fg="yellow", nl=False)
        click.secho(f"{file_name}", fg="white", bold=True)
        
        click.secho(" 📂 Thư mục lưu  : ", fg="yellow", nl=False)
        click.secho(f"{dir_name}", fg="white")
        
        click.secho("───────────────────────────────────────────────────", fg="cyan")
        click.secho("✅ Đã lưu xong! Mở lên và chốt đơn thôi sếp ơi!", fg="green", bold=True)

    sys.exit(0)
