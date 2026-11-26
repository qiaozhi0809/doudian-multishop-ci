"""通知中心表：notification（事件与强状态）与 sync_baseline（首次同步基线）。"""

import sqlalchemy as sa

from app.store.schema import _NOW, _id, metadata

notification = sa.Table(
    "notification",
    metadata,
    _id(),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column("level", sa.Text, nullable=False),
    sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id")),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("body", sa.Text),
    sa.Column("link", sa.Text),
    sa.Column("count", sa.Integer, nullable=False, server_default="1"),
    sa.Column("state_key", sa.Text),
    sa.Column("resolved_at", _NOW),
    sa.Column("read_at", _NOW),
    sa.Column("recovered_notified_at", _NOW),  # 强状态已写过「已恢复」（重开后不再写）
    sa.Column("created_at", _NOW, nullable=False),
    sa.Column("updated_at", _NOW, nullable=False),
)
sa.Index("idx_notification_unread", notification.c.read_at, notification.c.created_at)
# 同一强状态解决前只允许一条；解决后可再次出现
sa.Index(
    "uq_notification_open_state",
    notification.c.state_key,
    unique=True,
    sqlite_where=sa.text("state_key IS NOT NULL AND resolved_at IS NULL"),
)

sync_baseline = sa.Table(
    "sync_baseline",
    metadata,
    sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id"), primary_key=True),
    sa.Column("kind", sa.Text, primary_key=True),
    sa.Column("established_at", _NOW, nullable=False),
)
