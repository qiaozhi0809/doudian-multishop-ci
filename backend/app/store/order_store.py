"""orders / order_items 读写。本地 status 只由 set_local_status 修改，平台同步不覆盖。"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

import sqlalchemy as sa

from app.domain.models import OrderDTO
from app.domain.order_status import LOCAL_FINAL_STATUSES, PLATFORM_FINAL_STATUSES, LocalOrderStatus
from app.store.schema import order_items, orders


def _platform_values(o: OrderDTO, now: str) -> dict[str, Any]:
    return {
        "platform_order_id": o.platform_order_id, "combine_id": o.combine_id,
        "platform_status": o.platform_status, "buyer_nick": o.buyer_nick,
        "receiver_name": o.receiver_name, "receiver_phone": o.receiver_phone,
        "receiver_region": o.receiver_region, "amount_cents": o.amount_cents,
        "pay_time": o.pay_time, "create_time": o.create_time, "exp_ship_time": o.exp_ship_time,
        "raw_json": json.dumps(o.raw, ensure_ascii=False),
        "synced_at": now, "last_sync_at": now,
    }


def upsert_orders(conn: sa.Connection, shop_id: int, items: Sequence[OrderDTO], now: str) -> int:
    for o in items:
        values = _platform_values(o, now)
        order_id = conn.execute(
            sa.select(orders.c.id).where(
                orders.c.shop_id == shop_id, orders.c.order_no == o.order_no
            )
        ).scalar()
        if order_id is None:
            order_id = conn.execute(sa.insert(orders).values(
                shop_id=shop_id, order_no=o.order_no,
                status=LocalOrderStatus.SYNCED.value, **values,
            )).inserted_primary_key[0]
        else:
            conn.execute(sa.update(orders).where(orders.c.id == order_id).values(**values))
            conn.execute(sa.delete(order_items).where(order_items.c.order_id == order_id))
        if o.items:
            conn.execute(sa.insert(order_items), [
                {
                    "order_id": order_id, "sku_order_id": i.sku_order_id, "sku_id": i.sku_id,
                    "product_id": i.product_id, "product_name": i.product_name,
                    "sku_spec": i.sku_spec, "quantity": i.quantity, "price_cents": i.price_cents,
                }
                for i in o.items
            ])
    return len(items)


def set_local_status(
    conn: sa.Connection, shop_id: int, order_no: str, status: LocalOrderStatus, now: str
) -> None:
    conn.execute(
        sa.update(orders)
        .where(orders.c.shop_id == shop_id, orders.c.order_no == order_no)
        .values(status=str(status.value), last_sync_at=now)
    )


def list_orders(
    conn: sa.Connection, shop_ids: Sequence[int] | None, status: LocalOrderStatus | None,
    page: int, page_size: int,
) -> tuple[Sequence[Mapping[str, Any]], int]:
    """shop_ids 为 None 表示全部店铺，空序列表示没有店铺；page 从 1 起；按支付时间倒序。"""
    if shop_ids is not None and len(shop_ids) == 0:
        return [], 0
    cond = []
    if shop_ids is not None:
        cond.append(orders.c.shop_id.in_(shop_ids))
    if status is not None:
        cond.append(orders.c.status == str(status.value))
    total = conn.execute(sa.select(sa.func.count()).select_from(orders).where(*cond)).scalar_one()
    rows = conn.execute(
        sa.select(orders).where(*cond)
        .order_by(orders.c.pay_time.desc(), orders.c.id.desc())
        .limit(page_size).offset((page - 1) * page_size)
    ).mappings().all()
    return [dict(r) for r in rows], int(total)


def recheck_candidates(conn: sa.Connection, shop_id: int) -> set[str]:
    """本地未完结且平台状态不是 3 / 4 / 5 的单号。"""
    local_final = [s.value for s in LOCAL_FINAL_STATUSES]
    stmt = sa.select(orders.c.order_no).where(
        orders.c.shop_id == shop_id,
        orders.c.status.not_in(local_final),
        sa.or_(
            orders.c.platform_status.is_(None),
            orders.c.platform_status.not_in(sorted(PLATFORM_FINAL_STATUSES)),
        ),
    )
    return set(conn.execute(stmt).scalars())
