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
    sa.Column("egress_ip", sa.Text),
    sa.Column("egress_status", sa.Text, nullable=False, server_default="unchecked"),
    sa.Column("egress_checked_at", _NOW),
    sa.Column("egress_ip_pending", sa.Text),
    sa.Column("paused_reason", sa.Text),
    sa.Column("paused_at", _NOW),
    sa.Column("created_at", _NOW, nullable=False),
    sa.Column("updated_at", _NOW, nullable=False),
    # 迁移 0008：代理信息只存在 proxy_pool，shop 只记引用
    sa.Column("proxy_pool_id", sa.Integer, sa.ForeignKey("proxy_pool.id")),
    # 迁移 0012：接收飞鸽消息开关，默认关
    sa.Column("im_enabled", sa.Integer, nullable=False, server_default="0"),
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
# 一个池项同时只给一家启用店铺用；停用店铺不占位
sa.Index(
    "uq_shop_pool",
    shop.c.proxy_pool_id,
    unique=True,
    sqlite_where=sa.text("proxy_pool_id IS NOT NULL AND status != 'disabled'"),
)

# ---- 代理池（proxy-pool 设计 1.1）：账号密码只以 SecretBox 密文存在 proxy_url ----

proxy_pool = sa.Table(
    "proxy_pool",
    metadata,
    _id(),
    sa.Column("identity", sa.Text, nullable=False, unique=True),
    sa.Column("proxy_url", sa.LargeBinary, nullable=False),
    sa.Column("proxy_display", sa.Text, nullable=False),
    sa.Column("expires_at", sa.Text),  # YYYY-MM-DD，空表示不限
    sa.Column("last_checked_at", _NOW),
    sa.Column("last_check_ip", sa.Text),
    sa.Column("created_at", _NOW, nullable=False),
    sa.Column("updated_at", _NOW, nullable=False),
)

shop_profile = sa.Table(
    "shop_profile",
    metadata,
    sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id"), primary_key=True),
    sa.Column("qual_id", sa.Text),
    sa.Column("shop_name", sa.Text),
    sa.Column("shop_type", sa.Integer),
    sa.Column("operate_status_str", sa.Text),
    sa.Column("open_time", sa.Text),
    sa.Column("settle_delay", sa.Text),
    sa.Column("admin_name", sa.Text),
    sa.Column("admin_mobile", sa.Text),  # 平台只返回脱敏值
    # 迁移 0010：平台侧无稳定接口，支持手工维护；抓取仅作首次兜底
    sa.Column("platform_shop_id", sa.Text),
    sa.Column("bank_name", sa.Text),
    sa.Column("bank_tail", sa.Text),  # 只存卡号后四位
    sa.Column("raw_json", sa.Text),
    sa.Column("synced_at", _NOW, nullable=False),
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
    sa.Column("is_custom", sa.Integer, nullable=False, server_default="0"),
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

admin_user = sa.Table(
    "admin_user",
    metadata,
    _id(),
    sa.Column("username", sa.Text, nullable=False, unique=True),
    sa.Column("password_hash", sa.Text, nullable=False),
    sa.Column("failed_attempts", sa.Integer, nullable=False, server_default="0"),
    sa.Column("locked_until", _NOW),
    sa.Column("password_changed_at", _NOW, nullable=False),
    sa.Column("created_at", _NOW, nullable=False),
)

admin_session = sa.Table(
    "admin_session",
    metadata,
    sa.Column("token_hash", sa.Text, primary_key=True),
    sa.Column(
        "user_id", sa.Integer, sa.ForeignKey("admin_user.id", ondelete="CASCADE"), nullable=False
    ),
    sa.Column("created_at", _NOW, nullable=False),
    sa.Column("last_seen_at", _NOW, nullable=False),
    sa.Column("expires_at", _NOW, nullable=False),
)
sa.Index("idx_admin_session_user", admin_session.c.user_id)

# ---- M2：面单与任务（data-model 6.2 ⑤⑥） ----

waybills = sa.Table(
    "waybills",
    metadata,
    _id(),
    _shop_fk(),
    sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=False),
    sa.Column("seq", sa.Integer, nullable=False, server_default="1"),
    sa.Column("courier_code", sa.Text, nullable=False),
    sa.Column("waybill_no", sa.Text),
    sa.Column("print_data", sa.Text),
    sa.Column("sign", sa.Text),
    sa.Column("logistics_template_code", sa.Text),
    sa.Column("exp_type", sa.Text),
    sa.Column("ebill_id", sa.Text),
    sa.Column("net_code", sa.Text),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("obtained_at", _NOW),
    sa.Column("printed_at", _NOW),
    sa.Column("voided_at", _NOW),
)
sa.Index("idx_waybills_order", waybills.c.order_id, waybills.c.status)
# 同一订单同时只能有一张有效面单；printed 也占名额，防「已打印未发货」重复取号
sa.Index(
    "uq_active_waybill", waybills.c.order_id, unique=True,
    sqlite_where=sa.text("status IN ('active','printed')"),
)
# 运单号全局唯一：本地发货防重（ship 幂等键）的数据库兜底
sa.Index(
    "uq_waybill_no", waybills.c.courier_code, waybills.c.waybill_no, unique=True,
    sqlite_where=sa.text("waybill_no IS NOT NULL"),
)

tasks = sa.Table(
    "tasks",
    metadata,
    _id(),
    sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id")),
    sa.Column("type", sa.Text, nullable=False),
    sa.Column("payload", sa.Text),
    sa.Column("idempotency_key", sa.Text, unique=True),
    sa.Column("created_by", sa.Text),
    sa.Column("status", sa.Text, nullable=False, server_default="queued"),
    sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
    sa.Column("last_error", sa.Text),
    sa.Column("created_at", _NOW, nullable=False),
    sa.Column("started_at", _NOW),
    sa.Column("finished_at", _NOW),
)
sa.Index("idx_tasks_status", tasks.c.status, tasks.c.created_at)

# ---- M3：打印任务（data-model 6.2 ⑤-b） ----

print_job = sa.Table(
    "print_job",
    metadata,
    _id(),
    sa.Column("waybill_id", sa.Integer, sa.ForeignKey("waybills.id"), nullable=False),
    sa.Column("printer_name", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False, server_default="queued"),
    sa.Column("result_code", sa.Text),
    sa.Column("result_detail", sa.Text),
    sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
    sa.Column("created_at", _NOW, nullable=False),
    sa.Column("finished_at", _NOW),
)
sa.Index("idx_print_job_waybill", print_job.c.waybill_id, print_job.c.created_at.desc())
