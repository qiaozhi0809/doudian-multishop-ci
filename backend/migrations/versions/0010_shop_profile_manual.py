"""店铺画像补充可手工维护的固定信息

Revision ID: 0010
Revises: 0009

平台侧三类信息在页面上可见但取数不稳定：
- 店铺ID：来自抖店前端全局 store，无 HTTP 接口
- 主体：资质页是微应用，无头渲染不稳定
- 提现卡：服务端渲染，可稳定抓取，但只保存开户行与尾号

因此这三项都支持手工填写（编辑店铺），抓取仅作首次兜底。
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shop_profile", sa.Column("platform_shop_id", sa.Text))
    op.add_column("shop_profile", sa.Column("bank_name", sa.Text))
    op.add_column("shop_profile", sa.Column("bank_tail", sa.Text))


def downgrade() -> None:
    op.drop_column("shop_profile", "bank_tail")
    op.drop_column("shop_profile", "bank_name")
    op.drop_column("shop_profile", "platform_shop_id")
