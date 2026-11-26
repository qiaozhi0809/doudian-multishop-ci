"""sync_baseline 表：某店铺某类数据是否已完成首次同步。无业务判断。"""

import sqlalchemy as sa

from app.store.notification_schema import sync_baseline


def has(conn: sa.Connection, shop_id: int, kind: str) -> bool:
    return conn.execute(
        sa.select(sa.literal(1)).where(
            sync_baseline.c.shop_id == shop_id, sync_baseline.c.kind == kind
        )
    ).first() is not None


def establish(conn: sa.Connection, shop_id: int, kind: str, now: str) -> None:
    """幂等：已存在则保持原 established_at。"""
    if has(conn, shop_id, kind):
        return
    conn.execute(sa.insert(sync_baseline).values(
        shop_id=shop_id, kind=kind, established_at=now,
    ))
