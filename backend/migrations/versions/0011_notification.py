"""通知中心：通知表与同步基线表

Revision ID: 0011
Revises: 0010

notification 同时承载「事件」（state_key 为空，一次性）与「强状态」（state_key 非空，
解决前同一 state_key 只能有一条未解决记录，由部分唯一索引保证）。
recovered_notified_at：该强状态已写过「已恢复」；30 分钟内重开后再恢复不再写。
sync_baseline 记录某店铺某类数据已完成首次同步，之后的新增才算新事件。
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("level", sa.Text, nullable=False),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id")),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("link", sa.Text),
        sa.Column("count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("state_key", sa.Text),
        sa.Column("resolved_at", sa.Text),
        sa.Column("read_at", sa.Text),
        sa.Column("recovered_notified_at", sa.Text),  # 强状态：已写过「已恢复」的时间
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
    )
    op.create_index("idx_notification_unread", "notification", ["read_at", "created_at"])
    op.execute(
        "CREATE UNIQUE INDEX uq_notification_open_state ON notification(state_key) "
        "WHERE state_key IS NOT NULL AND resolved_at IS NULL"
    )
    op.create_table(
        "sync_baseline",
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id"), primary_key=True),
        sa.Column("kind", sa.Text, primary_key=True),
        sa.Column("established_at", sa.Text, nullable=False),
    )


def downgrade() -> None:
    raise NotImplementedError("不支持降级")
