"""飞鸽消息只读聚合：店铺开关与消息记录表

Revision ID: 0012
Revises: 0011

shop.im_enabled 为「接收飞鸽消息」开关，默认关。
im_message 保存飞鸽推送解析出的消息，保留 30 天（按 captured_at 清理）；
同一店铺内 message_id 唯一，重复推送不重复写入。
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shop", sa.Column("im_enabled", sa.Integer, nullable=False, server_default="0")
    )
    op.create_table(
        "im_message",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("shop_id", sa.Integer, sa.ForeignKey("shop.id"), nullable=False),
        sa.Column("conversation_id", sa.Text, nullable=False),
        sa.Column("message_id", sa.Text, nullable=False),
        sa.Column("sender_role", sa.Text, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("sent_at", sa.Text, nullable=False),
        sa.Column("captured_at", sa.Text, nullable=False),
    )
    op.create_index(
        "uq_im_message_shop_msg", "im_message", ["shop_id", "message_id"], unique=True
    )
    op.create_index(
        "idx_im_message_conv", "im_message", ["shop_id", "conversation_id", "sent_at"]
    )
    op.create_index("idx_im_message_captured", "im_message", ["captured_at"])


def downgrade() -> None:
    op.drop_table("im_message")
    op.drop_column("shop", "im_enabled")
