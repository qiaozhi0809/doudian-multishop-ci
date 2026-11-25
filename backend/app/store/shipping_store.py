"""shipment 读写与发货订单池查询。状态推进由 service 决定，这里只做表操作。"""

from collections.abc import Mapping, Sequence
from typing import Any

import sqlalchemy as sa

from app.domain.shipping_rules import SHIPPABLE_STATUSES
from app.store.schema import orders, waybills
from app.store.shipping_schema import shipment

_ACTIVE_WAYBILL_STATUSES = ("active", "printed")


def list_pool(
    conn: sa.Connection, shop_ids: Sequence[int] | None, page: int, page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    """待发货订单池：本地状态可发货且有有效面单；按支付时间从早到晚（先发老单）。"""
    if shop_ids is not None and len(shop_ids) == 0:
        return [], 0
    cond = [orders.c.status.in_(sorted(SHIPPABLE_STATUSES))]
    if shop_ids is not None:
        cond.append(orders.c.shop_id.in_(shop_ids))
    base = (
        sa.select(orders, waybills.c.id.label("waybill_id"),
                  waybills.c.courier_code, waybills.c.waybill_no,
                  waybills.c.status.label("waybill_status"))
        .join(waybills, sa.and_(
            waybills.c.order_id == orders.c.id,
            waybills.c.status.in_(_ACTIVE_WAYBILL_STATUSES),
        ))
        .where(*cond)
    )
    total = conn.execute(
        sa.select(sa.func.count()).select_from(base.subquery())
    ).scalar_one()
    rows = conn.execute(
        base.order_by(orders.c.pay_time.asc(), orders.c.id.asc())
        .limit(page_size).offset((page - 1) * page_size)
    ).mappings()
    return [dict(r) for r in rows], int(total)


def insert_pending(
    conn: sa.Connection, rows: Sequence[Mapping[str, Any]], batch_id: str, now: str,
) -> None:
    """rows: 含 order_id / shop_id / waybill_id / courier_code / tracking_no。"""
    if not rows:
        return
    conn.execute(sa.insert(shipment), [
        {
            "batch_id": batch_id, "shop_id": r["shop_id"], "order_id": r["order_id"],
            "waybill_id": r.get("waybill_id"), "courier_code": r["courier_code"],
            "tracking_no": r["tracking_no"], "status": "pending", "created_at": now,
        }
        for r in rows
    ])


def finish_order(
    conn: sa.Connection, batch_id: str, order_id: int, status: str,
    fail_msg: str | None, now: str,
) -> None:
    conn.execute(
        sa.update(shipment).where(
            shipment.c.batch_id == batch_id, shipment.c.order_id == order_id,
            shipment.c.status == "pending",
        ).values(status=status, fail_msg=fail_msg, finished_at=now)
    )


def already_shipped_orders(
    conn: sa.Connection, shop_id: int, order_ids: Sequence[int],
) -> set[int]:
    """已有 success 记录的订单（数据库层防重）。"""
    if not order_ids:
        return set()
    rows = conn.execute(
        sa.select(shipment.c.order_id).where(
            shipment.c.shop_id == shop_id, shipment.c.order_id.in_(order_ids),
            shipment.c.status == "success",
        )
    ).scalars()
    return set(rows)


def mark_orders_shipped(
    conn: sa.Connection, shop_id: int, order_ids: Sequence[int], now: str,
) -> None:
    """只推进仍在可发货状态的订单；已被取消 / 关闭的订单不被发货结果覆盖。"""
    if not order_ids:
        return
    conn.execute(
        sa.update(orders).where(
            orders.c.shop_id == shop_id, orders.c.id.in_(list(order_ids)),
            orders.c.status.in_(sorted(SHIPPABLE_STATUSES)),
        ).values(status="shipped", last_sync_at=now)
    )


def by_batch(conn: sa.Connection, batch_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        sa.select(shipment).where(shipment.c.batch_id == batch_id).order_by(shipment.c.id)
    ).mappings()
    return [dict(r) for r in rows]
