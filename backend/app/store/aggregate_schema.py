"""M5 只读聚合表（data-model 6.2 ⑯~⑳）。迁移脚本 0003 与本文件逐列对应。

单独成文件是为了让 M1/M2 的 schema.py 保持不动；表仍注册在同一个 metadata 上，
迁移一致性测试（tests/store/migration_test.py）同时校验两个模块。
"""

import sqlalchemy as sa

from app.store.schema import _NOW, _id, _shop_fk, metadata

# ---- ⑯ 售后聚合（附录 E）----
aftersale = sa.Table(
    "aftersale",
    metadata,
    _id(),
    _shop_fk(),
    sa.Column("after_sale_id", sa.Text, nullable=False),
    sa.Column("order_no", sa.Text),
    sa.Column("type", sa.Integer),  # after_sale_type（平台数字枚举，取值未公开）
    sa.Column("status", sa.Integer),  # after_sale_status（同上）
    sa.Column("refund_amount_cents", sa.Integer),
    sa.Column("status_deadline", _NOW),  # 平台 unix 秒 → ISO-8601 UTC；0（已完结）→ NULL
    sa.Column("apply_time", _NOW),
    sa.Column("detail_json", sa.Text),
    sa.Column("synced_at", _NOW, nullable=False),
    sa.UniqueConstraint("shop_id", "after_sale_id"),
)
sa.Index("idx_aftersale_shop_deadline", aftersale.c.shop_id, aftersale.c.status_deadline)
sa.Index("idx_aftersale_order", aftersale.c.shop_id, aftersale.c.order_no)

# ---- ⑰ 商品快照（附录 D.1）----
product_snapshot = sa.Table(
    "product_snapshot",
    metadata,
    _id(),
    _shop_fk(),
    sa.Column("product_id", sa.Text, nullable=False),
    sa.Column("name", sa.Text),
    sa.Column("status", sa.Text),
    sa.Column("tab", sa.Text),
    sa.Column("price_lower_cents", sa.Integer),
    sa.Column("price_higher_cents", sa.Integer),
    sa.Column("stock_num", sa.Integer),
    sa.Column("sell_num", sa.Integer),
    sa.Column("raw_json", sa.Text),
    sa.Column("synced_at", _NOW, nullable=False),
    sa.UniqueConstraint("shop_id", "product_id"),
)
sa.Index("idx_products_shop_tab", product_snapshot.c.shop_id, product_snapshot.c.tab)

# ---- ⑱ 库存快照（附录 D.2）----
stock_snapshot = sa.Table(
    "stock_snapshot",
    metadata,
    _id(),
    _shop_fk(),
    sa.Column("product_id", sa.Text, nullable=False),
    sa.Column("total_stock_num", sa.Integer),
    sa.Column("spot_stock_num", sa.Integer),  # 现货
    sa.Column("future_stock_num", sa.Integer),  # 未来库存；不可与现货相加（附录 D.4）
    sa.Column("total_occupied_stock_num", sa.Integer),
    sa.Column("total_unoccupied_stock_num", sa.Integer),
    sa.Column("is_alarming", sa.Integer, nullable=False, server_default="0"),
    sa.Column("raw_json", sa.Text),
    sa.Column("synced_at", _NOW, nullable=False),
    sa.UniqueConstraint("shop_id", "product_id"),
)
sa.Index("idx_stock_shop_alarm", stock_snapshot.c.shop_id, stock_snapshot.c.is_alarming)

# ---- ⑲ 待结算订单（附录 F.1b）----
fund_unsettled = sa.Table(
    "fund_unsettled",
    metadata,
    _id(),
    _shop_fk(),
    sa.Column("shop_order_no", sa.Text, nullable=False),  # 唯一键列非空：SQLite 多个 NULL 互不冲突
    sa.Column("sku_order_no", sa.Text, nullable=False),
    sa.Column("product_id", sa.Text),
    sa.Column("income_amount_cents", sa.Integer),
    sa.Column("unsettled_amount_cents", sa.Integer),
    sa.Column("platform_service_fee_cents", sa.Integer),
    sa.Column("ecom_order_status", sa.Text),
    sa.Column("expected_settle_time", sa.Text),
    sa.Column("settle_period_detail", sa.Text),  # 平台 JSON 字符串，延迟天数从中读取
    sa.Column("raw_json", sa.Text),
    sa.Column("synced_at", _NOW, nullable=False),
    sa.UniqueConstraint("shop_id", "shop_order_no", "sku_order_no"),
)
sa.Index("idx_fund_unsettled_shop", fund_unsettled.c.shop_id)

# ---- ⑳ 保证金账户（附录 F.1c）----
margin_account = sa.Table(
    "margin_account",
    metadata,
    _id(),
    _shop_fk(),
    sa.Column("payable_cents", sa.Integer),
    sa.Column("balance_cents", sa.Integer),
    sa.Column("basic_payable_cents", sa.Integer),
    sa.Column("basic_balance_cents", sa.Integer),
    sa.Column("withdrawable_cents", sa.Integer),
    sa.Column("level", sa.Text),
    sa.Column("raw_json", sa.Text),
    sa.Column("synced_at", _NOW, nullable=False),
    sa.UniqueConstraint("shop_id"),
)
