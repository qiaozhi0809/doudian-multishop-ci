"""M1 的 9 张表（data-model 6.2）。迁移脚本 0001 与本文件逐列对应，migration_test 校验一致。"""

import sqlalchemy as sa

metadata = sa.MetaData()


def _id() -> sa.Column:
    return sa.Column("id", sa.Integer, primary_key=True)


def _shop_fk() -> sa.Column:
    return sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id"), nullable=False)


_NOW = sa.Text  # ISO-8601 UTC 文本

shop = sa.Table(
    "shop",
    metadata,
    _id(),
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
    sa.Column("egress_checked_at", _NOW),
    sa.Column("egress_ip_pending", sa.Text),
    sa.Column("proxy_expires_at", _NOW),
    sa.Column("paused_reason", sa.Text),
    sa.Column("paused_at", _NOW),
    sa.Column("created_at", _NOW, nullable=False),
    sa.Column("updated_at", _NOW, nullable=False),
)
sa.Index(
    "uq_shop_direct",
    shop.c.egress_mode,
    unique=True,
    sqlite_where=sa.text("egress_mode = 'direct' AND status != 'disabled'"),
)
sa.Index(
    "uq_shop_egress_ip",
    shop.c.egress_ip,
    unique=True,
    sqlite_where=sa.text("egress_ip IS NOT NULL AND status != 'disabled'"),
)

session = sa.Table(
    "session",
    metadata,
    _id(),
    _shop_fk(),
    sa.Column("cookies", sa.LargeBinary),
    sa.Column("token", sa.LargeBinary),
    sa.Column("device_params", sa.Text),
    sa.Column("js_version", sa.Text),
    sa.Column("expires_at", _NOW),
    sa.Column("health", sa.Text, nullable=False, server_default="healthy"),
    sa.Column("updated_at", _NOW, nullable=False),
)
sa.Index("idx_session_shop", session.c.shop_id, session.c.updated_at.desc())

orders = sa.Table(
    "orders",
    metadata,
    _id(),
    _shop_fk(),
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
    sa.Column("pay_time", _NOW),
    sa.Column("create_time", _NOW),
    sa.Column("exp_ship_time", _NOW),
    sa.Column("logistics_status", sa.Text),
    sa.Column("raw_json", sa.Text),
    sa.Column("synced_at", _NOW, nullable=False),
    sa.Column("last_sync_at", _NOW),
    sa.UniqueConstraint("shop_id", "order_no"),
)
sa.Index("idx_orders_status", orders.c.status, orders.c.shop_id)
sa.Index("idx_orders_platform_status", orders.c.platform_status, orders.c.shop_id)
sa.Index("idx_orders_paytime", orders.c.pay_time)

order_items = sa.Table(
    "order_items",
    metadata,
    _id(),
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
sa.Index("idx_items_order", order_items.c.order_id)

shop_address = sa.Table(
    "shop_address",
    metadata,
    _id(),
    _shop_fk(),
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
    sa.Column("synced_at", _NOW, nullable=False),
    sa.UniqueConstraint("shop_id", "address_id"),
)

ebill_account = sa.Table(
    "ebill_account",
    metadata,
    _id(),
    _shop_fk(),
    sa.Column("courier_code", sa.Text, nullable=False),
    sa.Column("ebill_id", sa.Text, nullable=False),
    sa.Column("net_code", sa.Text, nullable=False),
    sa.Column("net_name", sa.Text),
    sa.Column("account_type", sa.Integer),
    sa.Column("balance", sa.Integer),
    sa.Column("is_default", sa.Integer, nullable=False, server_default="0"),
    sa.Column("raw_json", sa.Text),
    sa.Column("synced_at", _NOW, nullable=False),
    sa.UniqueConstraint("shop_id", "courier_code", "ebill_id", "net_code"),
)

waybill_template = sa.Table(
    "waybill_template",
    metadata,
    _id(),
    _shop_fk(),
    sa.Column("template_code", sa.Text, nullable=False),
    sa.Column("courier_code", sa.Text),
    sa.Column("name", sa.Text),
    sa.Column("is_default", sa.Integer, nullable=False, server_default="0"),
    sa.Column("raw_json", sa.Text),
    sa.Column("synced_at", _NOW, nullable=False),
    sa.UniqueConstraint("shop_id", "template_code"),
)

courier = sa.Table(
    "courier",
    metadata,
    _id(),
    _shop_fk(),
    sa.Column("courier_code", sa.Text, nullable=False),
    sa.Column("name", sa.Text),
    sa.Column("enabled", sa.Integer, nullable=False, server_default="1"),
    sa.Column("raw_json", sa.Text),
    sa.Column("synced_at", _NOW, nullable=False),
    sa.UniqueConstraint("shop_id", "courier_code"),
)

audit_log = sa.Table(
    "audit_log",
    metadata,
    _id(),
    sa.Column("shop_id", sa.Integer),
    sa.Column("task_id", sa.Integer),
    sa.Column("actor", sa.Text),
    sa.Column("action", sa.Text, nullable=False),
    sa.Column("req_summary", sa.Text),
    sa.Column("resp_summary", sa.Text),
    sa.Column("result", sa.Text, nullable=False),
    sa.Column("duration_ms", sa.Integer),
    sa.Column("created_at", _NOW, nullable=False),
)
sa.Index("idx_audit_time", audit_log.c.created_at)
sa.Index("idx_audit_shop", audit_log.c.shop_id, audit_log.c.created_at)
