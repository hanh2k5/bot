"""CLI gop command — Auto-deduplicate and clean up database in 1 click."""

from __future__ import annotations

import sys
import click


@click.command()
@click.pass_context
def quet_cmd(ctx: click.Context) -> None:
    """Tự động quét và gộp toàn bộ các SĐT trùng lặp trong CSDL."""
    config = ctx.obj["config"]

    try:
        from leadhunter.presentation.cli.factory import make_repository
        repo = make_repository(config)

        # Execute auto-dedup directly on repository database
        with repo._cm.connection() as conn:
            # Check total before
            cursor = conn.execute("SELECT COUNT(*) FROM leads")
            before = cursor.fetchone()[0]

            # Find duplicates count
            cursor.execute("""
                SELECT COUNT(*) FROM leads 
                WHERE rowid NOT IN (
                    SELECT MIN(rowid) 
                    FROM leads 
                    GROUP BY phone
                )
            """)
            dup_count = cursor.fetchone()[0]

            if dup_count == 0:
                click.echo()
                click.secho("✨ CSDL SẠCH BONG! Không có số điện thoại nào bị trùng lặp.", fg="green", bold=True)
                return

            # Execute deletion of duplicate rows
            conn.execute("""
                DELETE FROM leads 
                WHERE rowid NOT IN (
                    SELECT MIN(rowid) 
                    FROM leads 
                    GROUP BY phone
                )
            """)
            conn.commit()

            cursor = conn.execute("SELECT COUNT(*) FROM leads")
            after = cursor.fetchone()[0]

            click.echo()
            click.secho(f"✅ ĐÃ TỰ ĐỘNG GỘP VÀ XÓA SẠCH {dup_count} BẢN GHI TRÙNG LẶP!", fg="green", bold=True)
            click.secho(f"📊 Tổng số Lead sạch còn lại trong Database: {after} (Trước đó: {before})", fg="cyan")

    except Exception as exc:
        click.echo(f"Lỗi gộp CSDL: {exc}", err=True)
        sys.exit(1)
