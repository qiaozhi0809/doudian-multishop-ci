"""shop_profile 表 CRUD：登录后从平台同步的店铺资质与负责人。无业务判断。"""

from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa

from app.store.schema import shop_profile


def upsert(conn: sa.Connection, shop_id: int, now: str, **values: Any) -> None:
    """平台同步路径的写入，语义与 patch 相同：只覆盖给定列，未给的列保持原值；行不存在时补建。

    同步每次都给全部同步列，所以效果是「同步列整体刷新」，手工维护的店铺ID / 收款信息不受影响。
    未知列名抛 ValueError。
    """
    patch(conn, shop_id, now, **values)


def patch(conn: sa.Connection, shop_id: int, now: str, **values: Any) -> None:
    """只更新给定列；行不存在时补建。用于手工编辑与抓取兜底，不覆盖其它字段。"""
    unknown = set(values) - (set(shop_profile.c.keys()) - {"shop_id", "synced_at"})
    if unknown:
        raise ValueError(f"未知列: {sorted(unknown)}")
    exists = conn.execute(
        sa.select(shop_profile.c.shop_id).where(shop_profile.c.shop_id == shop_id)
    ).first()
    if exists:
        conn.execute(
            sa.update(shop_profile)
            .where(shop_profile.c.shop_id == shop_id)
            .values(**values, synced_at=now)
        )
    else:
        conn.execute(
            sa.insert(shop_profile).values(shop_id=shop_id, **values, synced_at=now)
        )


def get(conn: sa.Connection, shop_id: int) -> Mapping[str, Any] | None:
    row = conn.execute(
        sa.select(shop_profile).where(shop_profile.c.shop_id == shop_id)
    ).mappings().first()
    return dict(row) if row else None
