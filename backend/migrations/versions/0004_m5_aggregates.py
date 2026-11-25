"""M5 只读聚合表：aftersale / product_snapshot / stock_snapshot / fund_unsettled / margin_account

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
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
        "aftersale",
        _pk(),
        _shop_id(),
        sa.Column("after_sale_id", sa.Text, nullable=False),
        sa.Column("order_no", sa.Text),
        sa.Column("type", sa.Integer),
        sa.Column("status", sa.Integer),
        sa.Column("refund_amount_cents", sa.Integer),
        sa.Column("status_deadline", sa.Text),
        sa.Column("apply_time", sa.Text),
        sa.Column("detail_json", sa.Text),
        _synced(),
        sa.UniqueConstraint("shop_id", "after_sale_id"),
    )
    op.create_index(
        "idx_aftersale_shop_deadline", "aftersale", ["shop_id", "status_deadline"]
    )
    op.create_index("idx_aftersale_order", "aftersale", ["shop_id", "order_no"])

    op.create_table(
        "product_snapshot",
        _pk(),
        _shop_id(),
        sa.Column("product_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text),
        sa.Column("status", sa.Text),
        sa.Column("tab", sa.Text),
        sa.Column("price_lower_cents", sa.Integer),
        sa.Column("price_higher_cents", sa.Integer),
        sa.Column("stock_num", sa.Integer),
        sa.Column("sell_num", sa.Integer),
        sa.Column("raw_json", sa.Text),
        _synced(),
        sa.UniqueConstraint("shop_id", "product_id"),
    )
    op.create_index("idx_products_shop_tab", "product_snapshot", ["shop_id", "tab"])

    op.create_table(
        "stock_snapshot",
        _pk(),
        _shop_id(),
        sa.Column("product_id", sa.Text, nullable=False),
        sa.Column("total_stock_num", sa.Integer),
        sa.Column("spot_stock_num", sa.Integer),
        sa.Column("future_stock_num", sa.Integer),
        sa.Column("total_occupied_stock_num", sa.Integer),
        sa.Column("total_unoccupied_stock_num", sa.Integer),
        sa.Column("is_alarming", sa.Integer, nullable=False, server_default="0"),
        sa.Column("raw_json", sa.Text),
        _synced(),
        sa.UniqueConstraint("shop_id", "product_id"),
    )
    op.create_index("idx_stock_shop_alarm", "stock_snapshot", ["shop_id", "is_alarming"])

    op.create_table(
        "fund_unsettled",
        _pk(),
        _shop_id(),
        sa.Column("shop_order_no", sa.Text, nullable=False),
        sa.Column("sku_order_no", sa.Text, nullable=False),
        sa.Column("product_id", sa.Text),
        sa.Column("income_amount_cents", sa.Integer),
        sa.Column("unsettled_amount_cents", sa.Integer),
        sa.Column("platform_service_fee_cents", sa.Integer),
        sa.Column("ecom_order_status", sa.Text),
        sa.Column("expected_settle_time", sa.Text),
        sa.Column("settle_period_detail", sa.Text),
        sa.Column("raw_json", sa.Text),
        _synced(),
        sa.UniqueConstraint("shop_id", "shop_order_no", "sku_order_no"),
    )
    op.create_index("idx_fund_unsettled_shop", "fund_unsettled", ["shop_id"])

    op.create_table(
        "margin_account",
        _pk(),
        _shop_id(),
        sa.Column("payable_cents", sa.Integer),
        sa.Column("balance_cents", sa.Integer),
        sa.Column("basic_payable_cents", sa.Integer),
        sa.Column("basic_balance_cents", sa.Integer),
        sa.Column("withdrawable_cents", sa.Integer),
        sa.Column("level", sa.Text),
        sa.Column("raw_json", sa.Text),
        _synced(),
        sa.UniqueConstraint("shop_id"),
    )


def downgrade() -> None:
    raise NotImplementedError("本机单用户应用，不提供降级")
