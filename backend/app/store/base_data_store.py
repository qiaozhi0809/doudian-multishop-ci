"""基础数据（地址、面单账户、模板、快递）按各表自己的唯一键整体替换。"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from app.domain.models import AddressDTO, CourierDTO, EbillAccountDTO, TemplateDTO
from app.store.schema import courier, ebill_account, shop_address, waybill_template


def _raw(raw: dict) -> str:
    return json.dumps(raw, ensure_ascii=False)


def _replace(
    conn: sa.Connection, table: sa.Table, key_cols: Sequence[str], shop_id: int,
    rows: Sequence[dict[str, Any]], now: str,
) -> None:
    """按唯一键比对：存在则更新，不存在则插入，本次未出现的删除。"""
    key = lambda r: tuple(r[c] for c in key_cols)  # noqa: E731
    existing = {
        key(r): r["id"]
        for r in conn.execute(sa.select(table).where(table.c.shop_id == shop_id)).mappings()
    }
    seen = set()
    for r in rows:
        k = key(r)
        seen.add(k)
        values = {**r, "shop_id": shop_id, "synced_at": now}
        if k in existing:
            conn.execute(sa.update(table).where(table.c.id == existing[k]).values(**values))
        else:
            conn.execute(sa.insert(table).values(**values))
    stale = [i for k, i in existing.items() if k not in seen]
    if stale:
        conn.execute(sa.delete(table).where(table.c.id.in_(stale)))


def replace_addresses(
    conn: sa.Connection, shop_id: int, rows: Sequence[AddressDTO], now: str
) -> None:
    data = [
        {
            "address_id": a.address_id, "name": a.name, "phone": a.phone, "region": a.region,
            "detail": a.detail, "province_id": a.province_id, "province_name": a.province_name,
            "city_id": a.city_id, "city_name": a.city_name, "town_id": a.town_id,
            "town_name": a.town_name, "street_id": a.street_id, "street_name": a.street_name,
            "is_default": int(a.is_default), "raw_json": _raw(a.raw),
        }
        for a in rows
    ]
    _replace(conn, shop_address, ["address_id"], shop_id, data, now)


def replace_ebill_accounts(
    conn: sa.Connection, shop_id: int, rows: Sequence[EbillAccountDTO], now: str
) -> None:
    data = [
        {
            "courier_code": a.courier_code, "ebill_id": a.ebill_id, "net_code": a.net_code,
            "net_name": a.net_name, "account_type": a.account_type, "balance": a.balance,
            "is_default": int(a.is_default), "raw_json": _raw(a.raw),
        }
        for a in rows
    ]
    _replace(conn, ebill_account, ["courier_code", "ebill_id", "net_code"], shop_id, data, now)


def replace_templates(
    conn: sa.Connection, shop_id: int, rows: Sequence[TemplateDTO], now: str
) -> None:
    data = [
        {
            "template_code": t.template_code, "courier_code": t.courier_code, "name": t.name,
            "raw_json": _raw(t.raw),
        }
        for t in rows
    ]
    _replace(conn, waybill_template, ["template_code"], shop_id, data, now)


def replace_couriers(
    conn: sa.Connection, shop_id: int, rows: Sequence[CourierDTO], now: str
) -> None:
    data = [
        {"courier_code": c.courier_code, "name": c.name, "enabled": int(c.enabled),
         "raw_json": _raw(c.raw)}
        for c in rows
    ]
    _replace(conn, courier, ["courier_code"], shop_id, data, now)
