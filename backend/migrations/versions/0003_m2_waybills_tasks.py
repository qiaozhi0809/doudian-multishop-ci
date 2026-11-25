"""M2：waybills、tasks（data-model 6.2 ⑤⑥）

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "waybills",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id"), nullable=False),
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
        sa.Column("obtained_at", sa.Text),
        sa.Column("printed_at", sa.Text),
        sa.Column("voided_at", sa.Text),
    )
    op.create_index("idx_waybills_order", "waybills", ["order_id", "status"])
    op.create_index(
        "uq_active_waybill", "waybills", ["order_id"], unique=True,
        sqlite_where=sa.text("status IN ('active','printed')"),
    )
    op.create_index(
        "uq_waybill_no", "waybills", ["courier_code", "waybill_no"], unique=True,
        sqlite_where=sa.text("waybill_no IS NOT NULL"),
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id")),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("payload", sa.Text),
        sa.Column("idempotency_key", sa.Text, unique=True),
        sa.Column("created_by", sa.Text),
        sa.Column("status", sa.Text, nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.Column("started_at", sa.Text),
        sa.Column("finished_at", sa.Text),
    )
    op.create_index("idx_tasks_status", "tasks", ["status", "created_at"])


def downgrade() -> None:
    raise NotImplementedError("本机单用户应用，不提供降级")
