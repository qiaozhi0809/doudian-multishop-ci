"""shipment 发货记录（M4）：一次发货批次里逐单的成功 / 失败留痕。

`status=success` 的 (shop_id, order_id) 唯一：数据库层的「同一单只发一次」兜底；
真正的幂等键仍是 tasks.idempotency_key（ship:{shop_id}:{courier_code}:{tracking_no}）。
"""

import sqlalchemy as sa

from app.store.schema import _NOW, _id, _shop_fk, metadata

shipment = sa.Table(
    "shipment",
    metadata,
    _id(),
    _shop_fk(),
    sa.Column("batch_id", sa.Text, nullable=False),
    sa.Column("order_id", sa.Integer, sa.ForeignKey("orders.id"), nullable=False),
    sa.Column("waybill_id", sa.Integer, sa.ForeignKey("waybills.id")),
    sa.Column("courier_code", sa.Text, nullable=False),
    sa.Column("tracking_no", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False),  # pending | success | failed
    sa.Column("fail_msg", sa.Text),
    sa.Column("created_at", _NOW, nullable=False),
    sa.Column("finished_at", _NOW),
)
sa.Index("idx_shipment_batch", shipment.c.batch_id)
sa.Index("idx_shipment_order", shipment.c.shop_id, shipment.c.order_id)
sa.Index(
    "uq_shipment_success_order", shipment.c.shop_id, shipment.c.order_id, unique=True,
    sqlite_where=sa.text("status = 'success'"),
)
