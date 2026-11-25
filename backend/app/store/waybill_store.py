"""waybills 读写。状态推进由 service 决定，这里只做表操作。"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

import sqlalchemy as sa

from app.store.schema import waybills

ACTIVE_STATUSES = ("active", "printed")


def insert(
    conn: sa.Connection, *, shop_id: int, order_id: int, seq: int, courier_code: str,
    waybill_no: str, print_data: str | None, sign: str | None, template_code: str | None,
    exp_type: str | None, ebill_id: str | None, net_code: str | None, status: str, now: str,
) -> int:
    return int(conn.execute(sa.insert(waybills).values(
        shop_id=shop_id, order_id=order_id, seq=seq, courier_code=courier_code,
        waybill_no=waybill_no, print_data=print_data, sign=sign,
        logistics_template_code=template_code, exp_type=exp_type, ebill_id=ebill_id,
        net_code=net_code, status=status, obtained_at=now,
    )).inserted_primary_key[0])


def active_by_orders(
    conn: sa.Connection, order_ids: Sequence[int]
) -> dict[int, Mapping[str, Any]]:
    """每单当前有效面单（active / printed）；没有的订单不出现在结果里。"""
    if not order_ids:
        return {}
    rows = conn.execute(
        sa.select(waybills).where(
            waybills.c.order_id.in_(order_ids), waybills.c.status.in_(ACTIVE_STATUSES)
        )
    ).mappings()
    return {r["order_id"]: dict(r) for r in rows}


def list_by_orders(
    conn: sa.Connection, order_ids: Sequence[int]
) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {i: [] for i in order_ids}
    if not order_ids:
        return out
    rows = conn.execute(
        sa.select(waybills).where(waybills.c.order_id.in_(order_ids))
        .order_by(waybills.c.order_id, waybills.c.seq)
    ).mappings()
    for r in rows:
        out[r["order_id"]].append(dict(r))
    return out


def by_ids(conn: sa.Connection, ids: Sequence[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    rows = conn.execute(
        sa.select(waybills).where(waybills.c.id.in_(ids)).order_by(waybills.c.id)
    ).mappings()
    return [dict(r) for r in rows]


def voided_count(conn: sa.Connection, order_id: int) -> int:
    return int(conn.execute(
        sa.select(sa.func.count()).select_from(waybills).where(
            waybills.c.order_id == order_id, waybills.c.status == "void")
    ).scalar_one())


def mark_void(conn: sa.Connection, waybill_id: int, now: str) -> None:
    conn.execute(
        sa.update(waybills).where(waybills.c.id == waybill_id)
        .values(status="void", voided_at=now)
    )


def payload_json(data: Mapping[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)
