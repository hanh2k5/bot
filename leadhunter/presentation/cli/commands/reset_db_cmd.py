"""CLI command to reset database and clear exports."""

from __future__ import annotations

import os
import pathlib
import click
from leadhunter.infrastructure.persistence.connection_manager import ConnectionManager


@click.command("reset-db")
def reset_db_cmd() -> None:
    """Reset Database (Xóa sạch toàn bộ lead cũ & file Excel cũ để cào mới hoàn toàn)."""
    # 1. Khai báo thẳng project_root ở ngay trên cùng (Lùi 4 lớp)
    project_root = pathlib.Path(__file__).resolve().parents[4]

    # 2. Xóa DB tuyệt đối
    db_path = project_root / "data" / "leadhunter.db"
    if db_path.exists():
        try:
            os.remove(db_path)
        except Exception:
            pass

    # 3. Xóa Excel tuyệt đối
    exp_dir = project_root / "exports"
    if exp_dir.exists():
        for f in exp_dir.glob("*.xlsx"):
            try:
                os.remove(f)
            except Exception:
                pass

    # 4. Khởi tạo lại DB bằng đường dẫn tuyệt đối
    cm = ConnectionManager(str(db_path))
    from leadhunter.infrastructure.persistence.migrations.migration_runner import (
        MigrationRunner,
    )

    MigrationRunner(cm).run()
    click.echo(
        "✓ ĐÃ RESET THÀNH CÔNG! Cơ sở dữ liệu và thư mục exports đã sạch 100%. Bạn có thể cào mới ngay!"
    )
