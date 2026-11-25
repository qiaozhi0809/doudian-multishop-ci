"""M4：发货 shipment + 对账 order_fact / reconcile_run / reconcile_findings

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- 订单事实（dashboard.md 3.1；替代原 orders_snapshot，G.7）----
    op.create_table(
        "order_fact",
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id"), primary_key=True),
        sa.Column("shop_order_id", sa.Text, primary_key=True),
        sa.Column("platform_status", sa.Integer),
        sa.Column("user_id", sa.Text),
        sa.Column("pay_time", sa.Text),
        sa.Column("biz_date", sa.Text),
        sa.Column("pay_amount_cents", sa.Integer),
        sa.Column("goods_amount_cents", sa.Integer),
        sa.Column("promotion_cents", sa.Integer),
        sa.Column("post_cents", sa.Integer),
        sa.Column("receive_amount_cents", sa.Integer),
        sa.Column("exp_ship_time", sa.Text),
        sa.Column("ship_time", sa.Text),
        sa.Column("tracking_no", sa.Text),
        sa.Column("company_code", sa.Text),
        sa.Column("raw_json", sa.Text),
        sa.Column("first_seen_at", sa.Text, nullable=False),
        sa.Column("synced_at", sa.Text, nullable=False),
    )
    op.create_index("idx_fact_date", "order_fact", ["biz_date", "shop_id"])

    # ---- 对账批次 ----
    op.create_table(
        "reconcile_run",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.Text, nullable=False, unique=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("shop_ids", sa.Text),
        sa.Column("window_days", sa.Integer, nullable=False),
        sa.Column("started_at", sa.Text, nullable=False),
        sa.Column("finished_at", sa.Text),
        sa.Column("scanned", sa.Integer, nullable=False, server_default="0"),
        sa.Column("finding_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
    )
    op.create_index("idx_reconcile_run_started", "reconcile_run", ["started_at"])

    # ---- 对账异常 ----
    op.create_table(
        "reconcile_findings",
        sa.Column("id", sa.Integer, primary_key=True),
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
        sa.Column("status", sa.Text, nullable=False, server_default="open"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("handled_at", sa.Text),
    )
    op.create_index("idx_findings_run", "reconcile_findings", ["run_id", "kind"])
    op.create_index("idx_findings_shop", "reconcile_findings", ["shop_id", "status"])

    # ---- 发货记录 ----
    op.create_table(
        "shipment",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id"), nullable=False),
        sa.Column("batch_id", sa.Text, nullable=False),
        sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("waybill_id", sa.Integer, sa.ForeignKey("waybills.id")),
        sa.Column("courier_code", sa.Text, nullable=False),
        sa.Column("tracking_no", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("fail_msg", sa.Text),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("finished_at", sa.Text),
    )
    op.create_index("idx_shipment_batch", "shipment", ["batch_id"])
    op.create_index("idx_shipment_order", "shipment", ["shop_id", "order_id"])
    op.create_index(
        "uq_shipment_success_order", "shipment", ["shop_id", "order_id"], unique=True,
        sqlite_where=sa.text("status = 'success'"),
    )


def downgrade() -> None:
    raise NotImplementedError("本机单用户应用，不提供降级")
