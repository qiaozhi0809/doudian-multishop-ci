"""notification 表 CRUD 与查询。无业务判断（去重、聚合、保留策略由服务层决定）。"""

from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa

from app.store.notification_schema import notification as n

_UPDATABLE = frozenset({
    "kind", "title", "body", "link", "count", "level", "resolved_at", "read_at",
    "recovered_notified_at",
})


def _open_strong():
    return sa.and_(n.c.state_key.is_not(None), n.c.resolved_at.is_(None))


def _one(conn: sa.Connection, stmt: sa.Select) -> Mapping[str, Any] | None:
    row = conn.execute(stmt).mappings().first()
    return dict(row) if row else None


def insert(conn: sa.Connection, **fields: Any) -> int:
    """同一 state_key 已有未解决记录时抛 IntegrityError。"""
    res = conn.execute(sa.insert(n).values(**fields))
    return int(res.inserted_primary_key[0])


def get(conn: sa.Connection, notification_id: int) -> Mapping[str, Any] | None:
    return _one(conn, sa.select(n).where(n.c.id == notification_id))


def update(conn: sa.Connection, notification_id: int, now: str, **fields: Any) -> None:
    """只允许白名单列；未知列名抛 ValueError。"""
    unknown = set(fields) - _UPDATABLE
    if unknown:
        raise ValueError(f"不可修改的列: {sorted(unknown)}")
    if fields:
        conn.execute(
            sa.update(n).where(n.c.id == notification_id).values(**fields, updated_at=now)
        )


def open_state(conn: sa.Connection, state_key: str) -> Mapping[str, Any] | None:
    return _one(conn, sa.select(n).where(n.c.state_key == state_key, n.c.resolved_at.is_(None)))


def last_resolved_state(conn: sa.Connection, state_key: str) -> Mapping[str, Any] | None:
    """该 state_key 最近一次被解决的记录（resolved_at 最新）。"""
    return _one(
        conn,
        sa.select(n).where(n.c.state_key == state_key, n.c.resolved_at.is_not(None))
        .order_by(n.c.resolved_at.desc(), n.c.id.desc()).limit(1),
    )


def latest_unread_event(
    conn: sa.Connection, shop_id: int, kind: str, *, link: str | None = None
) -> Mapping[str, Any] | None:
    """该店铺该类型最近一条未读事件（state_key 为空）；给 link 时只找链接相同的。"""
    cond = [n.c.shop_id == shop_id, n.c.kind == kind,
            n.c.state_key.is_(None), n.c.read_at.is_(None)]
    if link is not None:
        cond.append(n.c.link == link)
    return _one(
        conn,
        sa.select(n).where(*cond).order_by(n.c.created_at.desc(), n.c.id.desc()).limit(1),
    )


def list_page(
    conn: sa.Connection, *, unread_only: bool, offset: int, limit: int
) -> tuple[list[dict[str, Any]], int]:
    cond = n.c.read_at.is_(None) if unread_only else sa.true()
    total = conn.execute(sa.select(sa.func.count()).select_from(n).where(cond)).scalar_one()
    rows = conn.execute(
        sa.select(n).where(cond).order_by(n.c.updated_at.desc(), n.c.id.desc())
        .offset(offset).limit(limit)
    ).mappings().all()
    return [dict(r) for r in rows], int(total)


def unread_count(conn: sa.Connection) -> int:
    return int(conn.execute(
        sa.select(sa.func.count()).select_from(n).where(n.c.read_at.is_(None))
    ).scalar_one())


def open_strong_states(conn: sa.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        sa.select(n).where(_open_strong()).order_by(n.c.id)
    ).mappings().all()
    return [dict(r) for r in rows]


def mark_read(conn: sa.Connection, notification_id: int, now: str) -> None:
    """未读才写入；已读保持原 read_at。"""
    conn.execute(
        sa.update(n).where(n.c.id == notification_id, n.c.read_at.is_(None))
        .values(read_at=now)
    )


def mark_all_read(conn: sa.Connection, now: str) -> None:
    conn.execute(sa.update(n).where(n.c.read_at.is_(None)).values(read_at=now))


def purge_read_events_before(conn: sa.Connection, cutoff: str) -> int:
    """删除 updated_at 早于 cutoff 的已读记录；未读与未解决的强状态一律保留。"""
    res = conn.execute(
        sa.delete(n).where(
            n.c.read_at.is_not(None), n.c.updated_at < cutoff, ~_open_strong()
        )
    )
    return int(res.rowcount)
