"""orders / order_items 读写。本地 status 只由 set_local_status 修改，平台同步不覆盖。"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

import sqlalchemy as sa

from app.domain.models import OrderDTO
from app.domain.order_status import (
    LOCAL_STATUS_DISPLAY_ORDER,
    PLATFORM_FINAL_STATUSES,
    PLATFORM_STATUS_DISPLAY_ORDER,
    RECHECK_EXCLUDED_STATUSES,
    LocalOrderStatus,
    PlatformOrderStatus,
)
from app.store.aggregate_schema import aftersale
from app.store.schema import order_items, orders
from app.store.sorting import SortOrder, order_by, rank_of, shop_name_of


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


# 订单列表 / 打单台可排序的列（接口层 Literal 与此一致，见 tests/api/list_sort_test.py）
ORDER_SORTS: dict[str, Any] = {
    "shop_name": shop_name_of(orders.c.shop_id),
    # 状态列按界面显示顺序排（不是按内部代码的字典序）
    "platform_status": rank_of(orders.c.platform_status, PLATFORM_STATUS_DISPLAY_ORDER),
    "status": rank_of(orders.c.status, LOCAL_STATUS_DISPLAY_ORDER),
    "amount_cents": orders.c.amount_cents,
    "pay_time": orders.c.pay_time,
    "exp_ship_time": orders.c.exp_ship_time,
}
POOL_SORTS: dict[str, Any] = {
    k: ORDER_SORTS[k] for k in ("shop_name", "status", "amount_cents", "pay_time")
}


# 计数卡快捷筛选（与 /api/orders/counts 的四项同名）：按平台状态与承诺发货时间在 SQL 里筛
ORDER_QUICK_FILTERS = ("stock_up", "exp_ship", "ship_delay", "in_aftersale")


def _quick_cond(quick: str, now: str, in_24h: str) -> Any:
    stock_up = orders.c.platform_status == int(PlatformOrderStatus.STOCK_UP)
    if quick == "stock_up":
        return stock_up
    if quick == "exp_ship":
        return sa.and_(stock_up, orders.c.exp_ship_time >= now, orders.c.exp_ship_time < in_24h)
    if quick == "ship_delay":
        return sa.and_(stock_up, orders.c.exp_ship_time < now)
    if quick == "in_aftersale":
        # 本地售后快照里有仍在流转（有处理截止时间）的售后单
        return sa.exists().where(
            aftersale.c.shop_id == orders.c.shop_id, aftersale.c.order_no == orders.c.order_no,
            aftersale.c.status_deadline.is_not(None))
    raise ValueError(f"未知的订单快捷筛选: {quick}")


def list_orders(
    conn: sa.Connection, shop_ids: Sequence[int] | None, status: LocalOrderStatus | None,
    page: int, page_size: int, sort: str | None = None, order: SortOrder = "asc",
    *, quick: str | None = None, now: str = "", in_24h: str = "",
) -> tuple[Sequence[Mapping[str, Any]], int]:
    """shop_ids 为 None 表示全部店铺，空序列表示没有店铺；page 从 1 起；默认按支付时间倒序。
    quick 是计数卡快捷筛选，时间类筛选需要 now / in_24h（ISO 字符串，与库里格式一致）。"""
    if shop_ids is not None and len(shop_ids) == 0:
        return [], 0
    cond = []
    if shop_ids is not None:
        cond.append(orders.c.shop_id.in_(shop_ids))
    if status is not None:
        cond.append(orders.c.status == str(status.value))
    if quick is not None:
        cond.append(_quick_cond(quick, now, in_24h))
    total = conn.execute(sa.select(sa.func.count()).select_from(orders).where(*cond)).scalar_one()
    rows = conn.execute(
        sa.select(orders).where(*cond)
        .order_by(*order_by(ORDER_SORTS, sort, order,
                            (orders.c.pay_time.desc(), orders.c.id.desc()), orders.c.id))
        .limit(page_size).offset((page - 1) * page_size)
    ).mappings().all()
    return [dict(r) for r in rows], int(total)


def recheck_candidates_by_age(conn: sa.Connection, shop_id: int) -> list[str]:
    """本地未完结（含未标记异常）且平台状态不是 3 / 4 / 5 的单号，按最近同步时间从旧到新。"""
    excluded = [s.value for s in RECHECK_EXCLUDED_STATUSES]
    stmt = sa.select(orders.c.order_no).where(
        orders.c.shop_id == shop_id,
        orders.c.status.not_in(excluded),
        sa.or_(
            orders.c.platform_status.is_(None),
            orders.c.platform_status.not_in(sorted(PLATFORM_FINAL_STATUSES)),
        ),
    ).order_by(orders.c.synced_at, orders.c.id)
    return list(conn.execute(stmt).scalars())


def recheck_candidates(conn: sa.Connection, shop_id: int) -> set[str]:
    return set(recheck_candidates_by_age(conn, shop_id))


def mark_exception(
    conn: sa.Connection, shop_id: int, order_no: str, reason: str, now: str
) -> None:
    conn.execute(
        sa.update(orders)
        .where(orders.c.shop_id == shop_id, orders.c.order_no == order_no)
        .values(status=LocalOrderStatus.EXCEPTION.value, exception_reason=reason, last_sync_at=now)
    )


def items_by_order(
    conn: sa.Connection, order_ids: Sequence[int]
) -> dict[int, list[Mapping[str, Any]]]:
    out: dict[int, list[Mapping[str, Any]]] = {i: [] for i in order_ids}
    if not order_ids:
        return out
    rows = conn.execute(
        sa.select(order_items).where(order_items.c.order_id.in_(order_ids)).order_by(order_items.c.id)
    ).mappings()
    for r in rows:
        out[r["order_id"]].append(dict(r))
    return out


def get_by_ids(conn: sa.Connection, order_ids: Sequence[int]) -> list[dict[str, Any]]:
    if not order_ids:
        return []
    rows = conn.execute(
        sa.select(orders).where(orders.c.id.in_(order_ids)).order_by(orders.c.id)
    ).mappings()
    return [dict(r) for r in rows]


def ship_deadline_due(
    conn: sa.Connection, statuses: Sequence[str], warn_until: str, limit: int = 200,
) -> list[dict[str, Any]]:
    """未发货且 exp_ship_time 不晚于 warn_until 的订单，按最紧急排序（ENG-07）。"""
    if len(statuses) == 0:
        return []
    rows = conn.execute(
        sa.select(orders).where(
            orders.c.status.in_(list(statuses)),
            orders.c.exp_ship_time.is_not(None),
            orders.c.exp_ship_time != "",
            orders.c.exp_ship_time <= warn_until,
        ).order_by(orders.c.exp_ship_time, orders.c.id).limit(limit)
    ).mappings()
    return [dict(r) for r in rows]


def pool_orders(
    conn: sa.Connection, shop_ids: Sequence[int] | None, statuses: Sequence[str],
    page: int, page_size: int, sort: str | None = None, order: SortOrder = "asc",
) -> tuple[list[dict[str, Any]], int]:
    """打单台订单池：按本地状态集合过滤，默认按支付时间从早到晚（先处理老单）。"""
    if shop_ids is not None and len(shop_ids) == 0:
        return [], 0
    cond = [orders.c.status.in_(list(statuses))]
    if shop_ids is not None:
        cond.append(orders.c.shop_id.in_(shop_ids))
    total = conn.execute(
        sa.select(sa.func.count()).select_from(orders).where(*cond)
    ).scalar_one()
    rows = conn.execute(
        sa.select(orders).where(*cond)
        .order_by(*order_by(POOL_SORTS, sort, order,
                            (orders.c.pay_time.asc(), orders.c.id.asc()), orders.c.id))
        .limit(page_size).offset((page - 1) * page_size)
    ).mappings()
    return [dict(r) for r in rows], int(total)
