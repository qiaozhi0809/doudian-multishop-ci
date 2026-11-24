"""shop 表 CRUD。无业务判断。"""

from collections.abc import Mapping, Sequence
from typing import Any

import sqlalchemy as sa

from app.store.schema import shop

_EGRESS_FIELDS = frozenset({
    "egress_mode", "proxy_url", "proxy_display", "egress_ip", "egress_status",
    "egress_checked_at", "egress_ip_pending", "proxy_expires_at",
})


def create(
    conn: sa.Connection, name: str, now: str, *, entity: str | None = None,
    shop_no: str | None = None, channel: str = "protocol",
) -> int:
    res = conn.execute(sa.insert(shop).values(
        name=name, entity=entity, shop_no=shop_no, channel=channel,
        created_at=now, updated_at=now,
    ))
    return int(res.inserted_primary_key[0])


def get(conn: sa.Connection, shop_id: int) -> Mapping[str, Any] | None:
    row = conn.execute(sa.select(shop).where(shop.c.id == shop_id)).mappings().first()
    return dict(row) if row else None


def list(conn: sa.Connection) -> Sequence[Mapping[str, Any]]:  # noqa: A001
    rows = conn.execute(sa.select(shop).order_by(shop.c.id)).mappings().all()
    return [dict(r) for r in rows]


def _update(conn: sa.Connection, shop_id: int, now: str, values: Mapping[str, Any]) -> None:
    conn.execute(
        sa.update(shop).where(shop.c.id == shop_id).values(**values, updated_at=now)
    )


def set_status(conn: sa.Connection, shop_id: int, status: str, now: str) -> None:
    _update(conn, shop_id, now, {"status": status})


def set_egress(conn: sa.Connection, shop_id: int, now: str, **fields: Any) -> None:
    """只更新出口相关列；未知列名抛 ValueError。"""
    unknown = set(fields) - _EGRESS_FIELDS
    if unknown:
        raise ValueError(f"非出口列: {sorted(unknown)}")
    if fields:
        _update(conn, shop_id, now, fields)


def set_paused(conn: sa.Connection, shop_id: int, reason: str | None, now: str) -> None:
    _update(conn, shop_id, now, {"paused_reason": reason, "paused_at": now if reason else None})


def update_fields(conn: sa.Connection, shop_id: int, now: str, **fields: Any) -> None:
    """改名 / 主体 / 通道等普通字段。只允许白名单列。"""
    unknown = set(fields) - {"name", "entity", "shop_no", "channel"}
    if unknown:
        raise ValueError(f"不可修改的列: {sorted(unknown)}")
    if fields:
        _update(conn, shop_id, now, fields)
