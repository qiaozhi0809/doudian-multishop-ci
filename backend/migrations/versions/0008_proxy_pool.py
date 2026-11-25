"""代理池：代理信息从 shop 迁入 proxy_pool（proxy-pool 设计 1.4）

Revision ID: 0008
Revises: 0007

不用 batch 模式：batch 会重建 shop 表，而 shop 被多张表外键引用。删列用原生
ALTER TABLE DROP COLUMN（SQLite ≥ 3.35）。迁移里拿不到 SecretBox，搬来的旧数据
identity 暂记为 legacy:<shop_id>，启动时由 ProxyPoolService.rehash_legacy 补算。
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proxy_pool",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("identity", sa.Text, nullable=False, unique=True),
        sa.Column("proxy_url", sa.LargeBinary, nullable=False),
        sa.Column("proxy_display", sa.Text, nullable=False),
        sa.Column("expires_at", sa.Text),
        sa.Column("last_checked_at", sa.Text),
        sa.Column("last_check_ip", sa.Text),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
    )
    op.execute("ALTER TABLE shop ADD COLUMN proxy_pool_id INTEGER REFERENCES proxy_pool(id)")

    # 每家带代理的店各建一项，原样复制密文，回填 proxy_pool_id
    conn = op.get_bind()
    shop_ids = conn.execute(
        sa.text("SELECT id FROM shop WHERE proxy_url IS NOT NULL ORDER BY id")
    ).scalars().all()
    for shop_id in shop_ids:
        conn.execute(sa.text(
            "INSERT INTO proxy_pool (identity, proxy_url, proxy_display, expires_at,"
            " created_at, updated_at)"
            " SELECT 'legacy:' || id, proxy_url, COALESCE(proxy_display, ''),"
            " proxy_expires_at, updated_at, updated_at FROM shop WHERE id = :id"
        ), {"id": shop_id})
        conn.execute(sa.text(
            "UPDATE shop SET proxy_pool_id ="
            " (SELECT id FROM proxy_pool WHERE identity = 'legacy:' || :id) WHERE id = :id"
        ), {"id": shop_id})

    op.execute("ALTER TABLE shop DROP COLUMN proxy_url")
    op.execute("ALTER TABLE shop DROP COLUMN proxy_display")
    op.execute("ALTER TABLE shop DROP COLUMN proxy_expires_at")
    op.execute(
        "CREATE UNIQUE INDEX uq_shop_pool ON shop(proxy_pool_id)"
        " WHERE proxy_pool_id IS NOT NULL AND status != 'disabled'"
    )


def downgrade() -> None:
    raise NotImplementedError("本机单用户应用，不提供降级")
