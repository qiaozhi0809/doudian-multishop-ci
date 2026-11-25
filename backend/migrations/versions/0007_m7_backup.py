"""M7：backup_run 备份快照记录（gaps ENG-06）

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backup_run",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("file_name", sa.Text, nullable=False, unique=True),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("trigger", sa.Text, nullable=False),
        sa.Column("actor", sa.Text),
        sa.Column("created_at", sa.Text, nullable=False),
    )
    op.create_index("idx_backup_created", "backup_run", ["created_at"])


def downgrade() -> None:
    raise NotImplementedError("本机单用户应用，不提供降级")
