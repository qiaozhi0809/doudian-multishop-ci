"""product_snapshot / stock_snapshot 读写（商品与库存聚合，附录 D）。"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from app.domain.aggregate_models import ProductDTO, StockDTO
from app.store.aggregate_schema import product_snapshot, stock_snapshot


def upsert_products(
    conn: sa.Connection, shop_id: int, items: Sequence[ProductDTO], now: str
) -> int:
    for p in items:
        values = {
            "name": p.name, "status": p.status, "tab": p.tab,
            "price_lower_cents": p.price_lower_cents,
            "price_higher_cents": p.price_higher_cents,
            "stock_num": p.stock_num, "sell_num": p.sell_num,
            "raw_json": json.dumps(p.raw, ensure_ascii=False), "synced_at": now,
        }
        row_id = conn.execute(
            sa.select(product_snapshot.c.id).where(
                product_snapshot.c.shop_id == shop_id,
                product_snapshot.c.product_id == p.product_id,
            )
        ).scalar()
        if row_id is None:
            conn.execute(sa.insert(product_snapshot).values(
                shop_id=shop_id, product_id=p.product_id, **values
            ))
        else:
            conn.execute(
                sa.update(product_snapshot).where(product_snapshot.c.id == row_id).values(**values)
            )
    return len(items)


def prune_products(conn: sa.Connection, shop_id: int, now: str) -> int:
    result = conn.execute(
        sa.delete(product_snapshot).where(
            product_snapshot.c.shop_id == shop_id, product_snapshot.c.synced_at != now
        )
    )
    return result.rowcount or 0


def list_products(
    conn: sa.Connection, shop_ids: Sequence[int], *, tab: str | None = None,
    keyword: str | None = None, page: int = 1, page_size: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    if not shop_ids:
        return [], 0
    conds: list[Any] = [product_snapshot.c.shop_id.in_(list(shop_ids))]
    if tab:
        conds.append(product_snapshot.c.tab == tab)
    if keyword:
        conds.append(product_snapshot.c.name.like(f"%{keyword}%"))
    total = conn.execute(
        sa.select(sa.func.count()).select_from(product_snapshot).where(*conds)
    ).scalar_one()
    rows = conn.execute(
        sa.select(product_snapshot).where(*conds)
        .order_by(product_snapshot.c.sell_num.desc(), product_snapshot.c.id.desc())
        .limit(page_size).offset((page - 1) * page_size)
    ).mappings().all()
    return [dict(r) for r in rows], int(total)


def latest_synced_at(conn: sa.Connection, shop_ids: Sequence[int]) -> dict[int, str]:
    if not shop_ids:
        return {}
    rows = conn.execute(
        sa.select(product_snapshot.c.shop_id, sa.func.max(product_snapshot.c.synced_at))
        .where(product_snapshot.c.shop_id.in_(list(shop_ids)))
        .group_by(product_snapshot.c.shop_id)
    )
    return {r[0]: r[1] for r in rows}


def upsert_stock(
    conn: sa.Connection, shop_id: int, items: Sequence[StockDTO], now: str
) -> int:
    for s in items:
        values = {
            "total_stock_num": s.total_stock_num,
            "spot_stock_num": s.spot_stock_num,
            "future_stock_num": s.future_stock_num,
            "total_occupied_stock_num": s.total_occupied_stock_num,
            "total_unoccupied_stock_num": s.total_unoccupied_stock_num,
            "is_alarming": 1 if s.is_alarming else 0,
            "raw_json": json.dumps(s.raw, ensure_ascii=False), "synced_at": now,
        }
        row_id = conn.execute(
            sa.select(stock_snapshot.c.id).where(
                stock_snapshot.c.shop_id == shop_id,
                stock_snapshot.c.product_id == s.product_id,
            )
        ).scalar()
        if row_id is None:
            conn.execute(sa.insert(stock_snapshot).values(
                shop_id=shop_id, product_id=s.product_id, **values
            ))
        else:
            conn.execute(
                sa.update(stock_snapshot).where(stock_snapshot.c.id == row_id).values(**values)
            )
    return len(items)


def prune_stock(conn: sa.Connection, shop_id: int, now: str) -> int:
    result = conn.execute(
        sa.delete(stock_snapshot).where(
            stock_snapshot.c.shop_id == shop_id, stock_snapshot.c.synced_at != now
        )
    )
    return result.rowcount or 0


def list_stock(
    conn: sa.Connection, shop_ids: Sequence[int], *, alarm_only: bool = False,
    page: int = 1, page_size: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """库存行左连商品快照取名称（stock_snapshot 无名称列）。"""
    if not shop_ids:
        return [], 0
    conds: list[Any] = [stock_snapshot.c.shop_id.in_(list(shop_ids))]
    if alarm_only:
        conds.append(stock_snapshot.c.is_alarming == 1)
    base = stock_snapshot.outerjoin(
        product_snapshot,
        sa.and_(
            product_snapshot.c.shop_id == stock_snapshot.c.shop_id,
            product_snapshot.c.product_id == stock_snapshot.c.product_id,
        ),
    )
    total = conn.execute(
        sa.select(sa.func.count()).select_from(stock_snapshot).where(*conds)
    ).scalar_one()
    rows = conn.execute(
        sa.select(
            stock_snapshot.c.id, stock_snapshot.c.shop_id, stock_snapshot.c.product_id,
            stock_snapshot.c.total_stock_num, stock_snapshot.c.spot_stock_num,
            stock_snapshot.c.future_stock_num, stock_snapshot.c.total_occupied_stock_num,
            stock_snapshot.c.total_unoccupied_stock_num, stock_snapshot.c.is_alarming,
            stock_snapshot.c.synced_at, product_snapshot.c.name,
        )
        .select_from(base).where(*conds)
        .order_by(stock_snapshot.c.is_alarming.desc(), stock_snapshot.c.id.desc())
        .limit(page_size).offset((page - 1) * page_size)
    ).mappings().all()
    return [dict(r) for r in rows], int(total)


def stock_summary(conn: sa.Connection, shop_ids: Sequence[int]) -> dict[str, int]:
    """本地预警汇总：总数 / 预警数 / 售罄数（total_stock_num = 0）。"""
    if not shop_ids:
        return {"total": 0, "alarm_count": 0, "sold_out_count": 0}
    conds = [stock_snapshot.c.shop_id.in_(list(shop_ids))]
    row = conn.execute(
        sa.select(
            sa.func.count(),
            sa.func.coalesce(sa.func.sum(stock_snapshot.c.is_alarming), 0),
            sa.func.coalesce(sa.func.sum(
                sa.case((stock_snapshot.c.total_stock_num == 0, 1), else_=0)
            ), 0),
        ).where(*conds)
    ).one()
    return {"total": int(row[0]), "alarm_count": int(row[1]), "sold_out_count": int(row[2])}
