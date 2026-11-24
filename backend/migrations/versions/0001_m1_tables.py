"""M1 表结构（data-model 6.2）

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _pk() -> sa.Column:
    return sa.Column("id", sa.Integer, primary_key=True)


def _shop_id() -> sa.Column:
    return sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id"), nullable=False)


def _synced() -> sa.Column:
    return sa.Column("synced_at", sa.Text, nullable=False)


def upgrade() -> None:
    op.create_table(
        "shop",
        _pk(),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("entity", sa.Text),
        sa.Column("platform", sa.Text, nullable=False, server_default="doudian"),
        sa.Column("shop_no", sa.Text),
        sa.Column("channel", sa.Text, nullable=False, server_default="protocol"),
        sa.Column("status", sa.Text, nullable=False, server_default="needs_login"),
        sa.Column("egress_mode", sa.Text),
        sa.Column("proxy_url", sa.LargeBinary),
        sa.Column("proxy_display", sa.Text),
        sa.Column("egress_ip", sa.Text),
        sa.Column("egress_status", sa.Text, nullable=False, server_default="unchecked"),
        sa.Column("egress_checked_at", sa.Text),
        sa.Column("egress_ip_pending", sa.Text),
        sa.Column("proxy_expires_at", sa.Text),
        sa.Column("paused_reason", sa.Text),
        sa.Column("paused_at", sa.Text),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("updated_at", sa.Text, nullable=False),
    )
    op.create_index(
        "uq_shop_direct", "shop", ["egress_mode"], unique=True,
        sqlite_where=sa.text("egress_mode = 'direct' AND status != 'disabled'"),
    )
    op.create_index(
        "uq_shop_egress_ip", "shop", ["egress_ip"], unique=True,
        sqlite_where=sa.text("egress_ip IS NOT NULL AND status != 'disabled'"),
    )

    op.create_table(
        "session",
        _pk(),
        _shop_id(),
        sa.Column("cookies", sa.LargeBinary),
        sa.Column("token", sa.LargeBinary),
        sa.Column("device_params", sa.Text),
        sa.Column("js_version", sa.Text),
        sa.Column("expires_at", sa.Text),
        sa.Column("health", sa.Text, nullable=False, server_default="healthy"),
        sa.Column("updated_at", sa.Text, nullable=False),
    )
    op.create_index("idx_session_shop", "session", ["shop_id", sa.text("updated_at DESC")])

    op.create_table(
        "orders",
        _pk(),
        _shop_id(),
        sa.Column("order_no", sa.Text, nullable=False),
        sa.Column("platform_order_id", sa.Text),
        sa.Column("combine_id", sa.Text),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("platform_status", sa.Integer),
        sa.Column("exception_reason", sa.Text),
        sa.Column("buyer_nick", sa.Text),
        sa.Column("receiver_name", sa.Text),
        sa.Column("receiver_phone", sa.Text),
        sa.Column("receiver_region", sa.Text),
        sa.Column("amount_cents", sa.Integer),
        sa.Column("pay_time", sa.Text),
        sa.Column("create_time", sa.Text),
        sa.Column("exp_ship_time", sa.Text),
        sa.Column("logistics_status", sa.Text),
        sa.Column("raw_json", sa.Text),
        _synced(),
        sa.Column("last_sync_at", sa.Text),
        sa.UniqueConstraint("shop_id", "order_no"),
    )
    op.create_index("idx_orders_status", "orders", ["status", "shop_id"])
    op.create_index("idx_orders_platform_status", "orders", ["platform_status", "shop_id"])
    op.create_index("idx_orders_paytime", "orders", ["pay_time"])

    op.create_table(
        "order_items",
        _pk(),
        sa.Column(
            "order_id", sa.Integer, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("sku_order_id", sa.Text),
        sa.Column("sku_id", sa.Text),
        sa.Column("product_id", sa.Text),
        sa.Column("product_name", sa.Text),
        sa.Column("sku_spec", sa.Text),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("price_cents", sa.Integer),
    )
    op.create_index("idx_items_order", "order_items", ["order_id"])

    op.create_table(
        "shop_address",
        _pk(),
        _shop_id(),
        sa.Column("address_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text),
        sa.Column("phone", sa.Text),
        sa.Column("region", sa.Text),
        sa.Column("detail", sa.Text),
        sa.Column("province_id", sa.Integer),
        sa.Column("province_name", sa.Text),
        sa.Column("city_id", sa.Integer),
        sa.Column("city_name", sa.Text),
        sa.Column("town_id", sa.Integer),
        sa.Column("town_name", sa.Text),
        sa.Column("street_id", sa.Integer),
        sa.Column("street_name", sa.Text),
        sa.Column("is_default", sa.Integer, nullable=False, server_default="0"),
        sa.Column("raw_json", sa.Text),
        _synced(),
        sa.UniqueConstraint("shop_id", "address_id"),
    )

    op.create_table(
        "ebill_account",
        _pk(),
        _shop_id(),
        sa.Column("courier_code", sa.Text, nullable=False),
        sa.Column("ebill_id", sa.Text, nullable=False),
        sa.Column("net_code", sa.Text, nullable=False),
        sa.Column("net_name", sa.Text),
        sa.Column("account_type", sa.Integer),
        sa.Column("balance", sa.Integer),
        sa.Column("is_default", sa.Integer, nullable=False, server_default="0"),
        sa.Column("raw_json", sa.Text),
        _synced(),
        sa.UniqueConstraint("shop_id", "courier_code", "ebill_id", "net_code"),
    )

    op.create_table(
        "waybill_template",
        _pk(),
        _shop_id(),
        sa.Column("template_code", sa.Text, nullable=False),
        sa.Column("courier_code", sa.Text),
        sa.Column("name", sa.Text),
        sa.Column("is_default", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_custom", sa.Integer, nullable=False, server_default="0"),
        sa.Column("raw_json", sa.Text),
        _synced(),
        sa.UniqueConstraint("shop_id", "template_code"),
    )

    op.create_table(
        "courier",
        _pk(),
        _shop_id(),
        sa.Column("courier_code", sa.Text, nullable=False),
        sa.Column("name", sa.Text),
        sa.Column("enabled", sa.Integer, nullable=False, server_default="1"),
        sa.Column("raw_json", sa.Text),
        _synced(),
        sa.UniqueConstraint("shop_id", "courier_code"),
    )

    op.create_table(
        "audit_log",
        _pk(),
        sa.Column("shop_id", sa.Integer),
        sa.Column("task_id", sa.Integer),
        sa.Column("actor", sa.Text),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("req_summary", sa.Text),
        sa.Column("resp_summary", sa.Text),
        sa.Column("result", sa.Text, nullable=False),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("created_at", sa.Text, nullable=False),
    )
    op.create_index("idx_audit_time", "audit_log", ["created_at"])
    op.create_index("idx_audit_shop", "audit_log", ["shop_id", "created_at"])


def downgrade() -> None:
    raise NotImplementedError("本机单用户应用，不提供降级")
