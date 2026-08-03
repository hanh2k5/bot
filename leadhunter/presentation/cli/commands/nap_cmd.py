"""CLI nap command — Restore/import leads from Excel files into database."""

from __future__ import annotations

import sys
from pathlib import Path
import click


@click.command()
@click.argument("file_path", required=False, default=None)
@click.pass_context
def nap_cmd(ctx: click.Context, file_path: str | None) -> None:
    """Nạp dữ liệu từ file Excel vào Database để khôi phục hoặc bổ sung Lead."""
    config = ctx.obj["config"]

    try:
        from leadhunter.presentation.cli.factory import make_repository
        from leadhunter.infrastructure.adapters.excel_reader_adapter import ExcelReaderAdapter
        from leadhunter.application.use_cases.import_leads_from_file import ImportLeadsFromFileUseCase
        from leadhunter.domain.services.dedup_service import DeduplicationConfig

        repo = make_repository(config)
        adapter = ExcelReaderAdapter()
        dedup_config = DeduplicationConfig()
        use_case = ImportLeadsFromFileUseCase(
            repository=repo,
            adapter=adapter,
            dedup_config=dedup_config,
            max_file_size_mb=config.ingestion.max_file_size_mb,
            actor=config.actor,
        )

        def _normalize_wsl_path(raw_path: str) -> Path:
            p_str = raw_path.strip().strip("'\"")
            import re
            match = re.match(r"^([a-zA-Z]):[\\/](.*)", p_str)
            if match:
                drive = match.group(1).lower()
                rest = match.group(2).replace("\\", "/")
                return Path(f"/mnt/{drive}/{rest}")
            return Path(p_str)

        files_to_import: list[Path] = []

        if file_path:
            p = _normalize_wsl_path(file_path)
            if not p.exists():
                if not p.name.endswith(".xlsx") and Path(str(p) + ".xlsx").exists():
                    p = Path(str(p) + ".xlsx")
                else:
                    in_exports = Path("exports") / p.name
                    if in_exports.exists():
                        p = in_exports
                    elif (Path("exports") / (p.name + ".xlsx")).exists():
                        p = Path("exports") / (p.name + ".xlsx")
                    else:
                        click.secho(f"❌ Không tìm thấy file hoặc thư mục: {file_path}", fg="red")
                        sys.exit(1)

            if p.is_dir():
                files_to_import = [
                    f for f in p.glob("*.xlsx")
                    if not f.name.startswith("~$") and not f.name.startswith(".~")
                ]
                if not files_to_import:
                    files_to_import = [
                        f for f in p.rglob("*.xlsx")
                        if not f.name.startswith("~$") and not f.name.startswith(".~")
                    ]
            else:
                files_to_import.append(p)
        else:
            # Auto-scan exports directory for all xlsx files (loại bỏ file rác tạm thời ~$ của Excel)
            export_dir = Path("exports")
            if export_dir.exists():
                files_to_import = [
                    f for f in export_dir.glob("*.xlsx")
                    if not f.name.startswith("~$") and not f.name.startswith(".~")
                ]

        if not files_to_import:
            click.secho("❌ Không tìm thấy file .xlsx nào trong thư mục exports/ để nạp.", fg="yellow")
            click.echo("Cú pháp dùng cụ thể: nap \"thư_mục/file.xlsx\"")
            return

        total_imported = 0
        total_skipped = 0

        click.echo()
        click.secho(f"📦 Đang nạp dữ liệu từ {len(files_to_import)} file Excel vào Database...", fg="cyan", bold=True)

        for target_file in files_to_import:
            try:
                result = use_case.execute(file_path=str(target_file))
                total_imported += result.success_count
                total_skipped += result.duplicate_count
                click.secho(f"  ✅ [{target_file.name}]: Thêm mới {result.success_count} lead (Bỏ trùng {result.duplicate_count})", fg="green")
            except Exception as e:
                click.secho(f"  ❌ [{target_file.name}] Lỗi: {e}", fg="red")

        click.echo()
        click.secho("🎉 HOÀN TẤT NẠP DỮ LIỆU!", fg="green", bold=True)
        click.secho(f"📊 Tổng số Lead đã nạp mới vào CSDL: {total_imported} (Bỏ qua {total_skipped} lead trùng)", fg="white")

    except Exception as exc:
        click.echo(f"Lỗi khi nạp dữ liệu: {exc}", err=True)
        sys.exit(1)
