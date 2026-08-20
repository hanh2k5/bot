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
    try:
        config = ctx.obj["config"]
        from leadhunter.presentation.cli.factory import make_repository

        repo = make_repository(config)
        deleted_count = repo.rollback_last_batch()

        if deleted_count > 0:
            click.secho(
                f"\n✅ Đã rollback thành công! Đã xóa sạch {deleted_count} leads từ đợt cào gần nhất ra khỏi Database.",
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
