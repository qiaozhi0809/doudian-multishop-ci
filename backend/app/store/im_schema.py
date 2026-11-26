"""飞鸽消息表：im_message（迁移 0012）。正文只存在本表，保留 30 天。"""

import sqlalchemy as sa

from app.store.schema import _NOW, _id, _shop_fk, metadata

im_message = sa.Table(
    "im_message",
    metadata,
    _id(),
    _shop_fk(),
    sa.Column("conversation_id", sa.Text, nullable=False),
    sa.Column("message_id", sa.Text, nullable=False),
    sa.Column("sender_role", sa.Text, nullable=False),  # buyer | agent | robot | platform
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("sent_at", _NOW, nullable=False),
    sa.Column("captured_at", _NOW, nullable=False),
)
# 同一店铺内消息 ID 唯一：重复推送不重复写入
sa.Index("uq_im_message_shop_msg", im_message.c.shop_id, im_message.c.message_id, unique=True)
sa.Index(
    "idx_im_message_conv",
    im_message.c.shop_id, im_message.c.conversation_id, im_message.c.sent_at,
)
sa.Index("idx_im_message_captured", im_message.c.captured_at)
