"""M7 备份表：每次成功的 SQLite 快照一条记录（gaps ENG-06）。

目录里的文件是事实来源，这张表记录触发方式与体积，便于界面展示与保留策略对账。
"""

import sqlalchemy as sa

from app.store.schema import _NOW, _id, metadata

backup_run = sa.Table(
    "backup_run",
    metadata,
    _id(),
    sa.Column("file_name", sa.Text, nullable=False, unique=True),
    sa.Column("size_bytes", sa.Integer, nullable=False),
    sa.Column("trigger", sa.Text, nullable=False),  # daily | manual
    sa.Column("actor", sa.Text),
    sa.Column("created_at", _NOW, nullable=False),
)
sa.Index("idx_backup_created", backup_run.c.created_at)
