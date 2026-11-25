"""proxy_pool 表 CRUD 与占用查询。无业务判断，不碰加密（proxy_url 始终是密文）。"""

from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa

from app.store.schema import proxy_pool, shop

_UPDATABLE = frozenset({
    "identity", "proxy_url", "proxy_display", "expires_at", "last_checked_at", "last_check_ip",
})
_LEGACY_PREFIX = "legacy:"
_DISABLED = "disabled"


def upsert(
    conn: sa.Connection, *, identity: str, proxy_url: bytes, proxy_display: str,
    expires_at: str | None, now: str,
) -> int:
    """按 identity 去重：已存在则只在 expires_at 非空时覆盖它；返回池项 id。"""
    existing = get_by_identity(conn, identity)
    if existing is not None:
        if expires_at is not None:
            update(conn, existing["id"], now, expires_at=expires_at)
        return int(existing["id"])
    res = conn.execute(sa.insert(proxy_pool).values(
        identity=identity, proxy_url=proxy_url, proxy_display=proxy_display,
        expires_at=expires_at, created_at=now, updated_at=now,
    ))
    return int(res.inserted_primary_key[0])


def get(conn: sa.Connection, pool_id: int) -> Mapping[str, Any] | None:
    row = conn.execute(
        sa.select(proxy_pool).where(proxy_pool.c.id == pool_id)
    ).mappings().first()
    return dict(row) if row else None


def get_by_identity(conn: sa.Connection, identity: str) -> Mapping[str, Any] | None:
    row = conn.execute(
        sa.select(proxy_pool).where(proxy_pool.c.identity == identity)
    ).mappings().first()
    return dict(row) if row else None


def list_with_usage(conn: sa.Connection) -> list[dict[str, Any]]:
    """池列 + 占用它的启用店铺（in_use_shop_id / in_use_shop_name，无则为 None）。"""
    on = sa.and_(shop.c.proxy_pool_id == proxy_pool.c.id, shop.c.status != _DISABLED)
    rows = conn.execute(
        sa.select(
            proxy_pool,
            shop.c.id.label("in_use_shop_id"),
            shop.c.name.label("in_use_shop_name"),
        ).select_from(proxy_pool.outerjoin(shop, on)).order_by(proxy_pool.c.id)
    ).mappings().all()
    return [dict(r) for r in rows]


def referrers(conn: sa.Connection, pool_id: int) -> list[Mapping[str, Any]]:
    """引用该池项的全部店铺（含停用）。"""
    rows = conn.execute(
        sa.select(shop.c.id, shop.c.name, shop.c.status)
        .where(shop.c.proxy_pool_id == pool_id).order_by(shop.c.id)
    ).mappings().all()
    return [dict(r) for r in rows]


def update(conn: sa.Connection, pool_id: int, now: str, **fields: Any) -> None:
    """只允许白名单列；未知列名抛 ValueError。"""
    unknown = set(fields) - _UPDATABLE
    if unknown:
        raise ValueError(f"不可修改的列: {sorted(unknown)}")
    if fields:
        conn.execute(
            sa.update(proxy_pool).where(proxy_pool.c.id == pool_id)
            .values(**fields, updated_at=now)
        )


def delete(conn: sa.Connection, pool_id: int) -> None:
    """仍被店铺引用时由外键约束拒绝（IntegrityError）。"""
    conn.execute(sa.delete(proxy_pool).where(proxy_pool.c.id == pool_id))


def list_legacy(conn: sa.Connection) -> list[Mapping[str, Any]]:
    """迁移搬来、identity 尚未补算的池项。"""
    rows = conn.execute(
        sa.select(proxy_pool).where(proxy_pool.c.identity.startswith(_LEGACY_PREFIX))
        .order_by(proxy_pool.c.id)
    ).mappings().all()
    return [dict(r) for r in rows]
