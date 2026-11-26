"""店铺画像：登录后从平台同步的资质与负责人信息

Revision ID: 0009
Revises: 0008

字段按 2026-11-26 实测响应定：
- `GET /center/qualification/shop/info?version=0` → qual_id / shop_name / shop_type /
  operate_status_str / shop_open_time_str / shop_settle_day.delay_day_display
- `GET /byteshop/shopuser/getAdminV2` → shop_charge_name / shop_charge_mobile（脱敏）

data-model.md 原先列的 main_category / address_* 等字段在该接口中并不存在，
等找到来源接口再补迁移。
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_profile",
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id"), primary_key=True),
        sa.Column("qual_id", sa.Text),
        sa.Column("shop_name", sa.Text),
        sa.Column("shop_type", sa.Integer),
        sa.Column("operate_status_str", sa.Text),
        sa.Column("open_time", sa.Text),
        sa.Column("settle_delay", sa.Text),
        sa.Column("admin_name", sa.Text),
        sa.Column("admin_mobile", sa.Text),
        sa.Column("raw_json", sa.Text),
        sa.Column("synced_at", sa.Text, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("shop_profile")
