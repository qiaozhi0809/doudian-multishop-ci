"""M4 对账表：订单事实 order_fact、对账批次 reconcile_run、异常 reconcile_findings。

`order_fact` 由仪表盘与对账共用（dashboard.md 3.1 / reconcile.md G.7），替代原 `orders_snapshot`；
`first_seen_at` 首次写入后不再更新，比较基准是本次同步之前的快照（G.4）。
"""

import sqlalchemy as sa

from app.store.schema import _NOW, _id, metadata

order_fact = sa.Table(
    "order_fact",
    metadata,
    sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id"), primary_key=True),
    sa.Column("shop_order_id", sa.Text, primary_key=True),
    sa.Column("platform_status", sa.Integer),
    sa.Column("user_id", sa.Text),
    sa.Column("pay_time", _NOW),
    sa.Column("biz_date", sa.Text),  # 北京时间日期（按 pay_time）
    sa.Column("pay_amount_cents", sa.Integer),
    sa.Column("goods_amount_cents", sa.Integer),
    sa.Column("promotion_cents", sa.Integer),
    sa.Column("post_cents", sa.Integer),
    sa.Column("receive_amount_cents", sa.Integer),
    sa.Column("exp_ship_time", _NOW),
    sa.Column("ship_time", _NOW),
    sa.Column("tracking_no", sa.Text),
    sa.Column("company_code", sa.Text),
    sa.Column("raw_json", sa.Text),
    sa.Column("first_seen_at", _NOW, nullable=False),
    sa.Column("synced_at", _NOW, nullable=False),
)
sa.Index("idx_fact_date", order_fact.c.biz_date, order_fact.c.shop_id)

reconcile_run = sa.Table(
    "reconcile_run",
    metadata,
    _id(),
    sa.Column("run_id", sa.Text, nullable=False, unique=True),
    sa.Column("status", sa.Text, nullable=False),  # running | success | failed
    sa.Column("shop_ids", sa.Text),  # JSON 数组
    sa.Column("window_days", sa.Integer, nullable=False),
    sa.Column("started_at", _NOW, nullable=False),
    sa.Column("finished_at", _NOW),
    sa.Column("scanned", sa.Integer, nullable=False, server_default="0"),
    sa.Column("finding_count", sa.Integer, nullable=False, server_default="0"),
    sa.Column("error", sa.Text),  # 失败店铺的错误摘要（不阻断其他店）
)
sa.Index("idx_reconcile_run_started", reconcile_run.c.started_at.desc())

reconcile_findings = sa.Table(
    "reconcile_findings",
    metadata,
    _id(),
    sa.Column("run_id", sa.Text, nullable=False),
    sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id"), nullable=False),
    sa.Column("shop_order_id", sa.Text, nullable=False),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column("local_status", sa.Integer),
    sa.Column("platform_status", sa.Integer),
    sa.Column("local_tracking_no", sa.Text),
    sa.Column("platform_tracking_no", sa.Text),
    sa.Column("local_company_code", sa.Text),
    sa.Column("platform_company_code", sa.Text),
    sa.Column("detail", sa.Text),
    sa.Column("status", sa.Text, nullable=False, server_default="open"),  # open | handled
    sa.Column("created_at", _NOW, nullable=False),
    sa.Column("handled_at", _NOW),
)
sa.Index("idx_findings_run", reconcile_findings.c.run_id, reconcile_findings.c.kind)
sa.Index("idx_findings_shop", reconcile_findings.c.shop_id, reconcile_findings.c.status)
