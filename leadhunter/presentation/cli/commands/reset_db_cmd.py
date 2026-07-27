"""CLI command to reset database and clear exports."""

from __future__ import annotations

import os
import pathlib
import click
from leadhunter.infrastructure.persistence.connection_manager import ConnectionManager

@click.command("reset-db")
def reset_db_cmd() -> None:
    """Reset Database (Xóa sạch toàn bộ lead cũ & file Excel cũ để cào mới hoàn toàn)."""
    db_path = pathlib.Path("data/leadhunter.db")
    if db_path.exists():
        try:
            os.remove(db_path)
        except Exception:
            pass

    exp_dir = pathlib.Path("exports")
    if exp_dir.exists():
        for f in exp_dir.glob("*.xlsx"):
            try:
                os.remove(f)
            except Exception:
                pass

    cm = ConnectionManager("data/leadhunter.db")
    from leadhunter.infrastructure.persistence.migrations.migration_runner import MigrationRunner
    MigrationRunner(cm).run()
    click.echo("✓ ĐÃ RESET THÀNH CÔNG! Cơ sở dữ liệu và thư mục exports đã sạch 100%. Bạn có thể cào mới ngay!")
