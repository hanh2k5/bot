"""CLI command to rollback the most recent auto-scrape batch."""

import click
import sys
from leadhunter.infrastructure.persistence.sqlite_lead_repository import (
    SqliteLeadRepository,
)


@click.command("rollback")
@click.pass_context
def rollback_cmd(ctx: click.Context) -> None:
    """Rollback (Xóa) toàn bộ dữ liệu của đợt cào tự động gần nhất."""
    config = ctx.obj["config"]

    try:
        from leadhunter.infrastructure.persistence.connection_manager import (
            ConnectionManager,
        )

        cm = ConnectionManager(config.database.path)
        repo = SqliteLeadRepository(cm)

        deleted_count = repo.rollback_last_batch()

        if deleted_count > 0:
            import os
            import glob

            deleted_file_msg = ""
            from pathlib import Path

            project_root = Path(__file__).resolve().parents[4]
            # Ép glob tìm đúng thư mục tuyệt đối
            export_files = glob.glob(str(project_root / "exports" / "*.xlsx"))
            if export_files:
                # Find the newest file by creation/modification time
                latest_file = max(export_files, key=os.path.getctime)
                try:
                    os.remove(latest_file)
                    deleted_file_msg = (
                        f"\n🗑️ Đã dọn dẹp luôn file Excel vừa xuất: {latest_file}"
                    )
                except Exception:
                    pass

            click.secho(
                f"\n✅ Đã rollback thành công! Đã xóa sạch {deleted_count} leads từ đợt cào gần nhất ra khỏi Database.{deleted_file_msg}",
                fg="green",
                bold=True,
            )
        else:
            click.secho(
                "\n⚠️ Không tìm thấy đợt cào nào để rollback, hoặc Database đang trống.",
                fg="yellow",
            )

    except Exception as exc:
        click.secho(f"Lỗi khi rollback: {str(exc)}", fg="red")
        sys.exit(1)
