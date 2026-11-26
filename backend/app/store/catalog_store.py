"""product_snapshot / stock_snapshot 读写（商品与库存聚合，附录 D）。"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from app.domain.aggregate_models import ProductDTO, StockDTO
from app.domain.product_status import PRODUCT_STATES, tab_aliases
from app.store.aggregate_schema import product_snapshot, stock_snapshot
from app.store.sorting import SortOrder, order_by, shop_name_of


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


_TAB = sa.func.lower(product_snapshot.c.tab)
# 状态列按界面顺序（在售 → 草稿 → 审核中 → 售罄 → 未通过 → 禁售 / 下架）排，同一口径的别名同名次
_TAB_RANK = sa.case(
    (product_snapshot.c.tab.is_(None), None),
    *[(_TAB.in_(aliases), i) for i, (_, _, aliases) in enumerate(PRODUCT_STATES)],
    else_=len(PRODUCT_STATES),
)

PRODUCT_SORTS: dict[str, Any] = {
    "shop_name": shop_name_of(product_snapshot.c.shop_id),
    "tab": _TAB_RANK,
    "price": product_snapshot.c.price_lower_cents,
    "stock_num": product_snapshot.c.stock_num,
    "sell_num": product_snapshot.c.sell_num,
    # 30 天销量只在平台原始报文里（展示选摘），用 SQLite JSON 函数取出排序
    # 平台可能给字符串 "12"：按整数排，和页面显示（opt_int）一致
    "sell_num_30d": sa.cast(
        sa.func.json_extract(product_snapshot.c.raw_json, "$.sell_num_30d"), sa.Integer),
}


def list_products(
    conn: sa.Connection, shop_ids: Sequence[int], *, tab: str | None = None,
    keyword: str | None = None, page: int = 1, page_size: int = 50,
    sort: str | None = None, order: SortOrder = "asc", quick: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """默认按销量倒序（快照里没有商品创建 / 更新时间）。quick 为计数卡快捷筛选（状态口径）。"""
    if not shop_ids:
        return [], 0
    conds: list[Any] = [product_snapshot.c.shop_id.in_(list(shop_ids))]
    if tab:
        conds.append(product_snapshot.c.tab == tab)
    if quick:
        conds.append(_TAB.in_(tab_aliases(quick)))
    if keyword:
        conds.append(product_snapshot.c.name.like(f"%{keyword}%"))
    total = conn.execute(
        sa.select(sa.func.count()).select_from(product_snapshot).where(*conds)
    ).scalar_one()
    rows = conn.execute(
        sa.select(product_snapshot).where(*conds)
        .order_by(*order_by(
            PRODUCT_SORTS, sort, order,
            (product_snapshot.c.sell_num.desc(), product_snapshot.c.id.desc()),
            product_snapshot.c.id,
        ))
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


STOCK_SORTS: dict[str, Any] = {
    "shop_name": shop_name_of(stock_snapshot.c.shop_id),
    "total_stock_num": stock_snapshot.c.total_stock_num,
    "spot_stock_num": stock_snapshot.c.spot_stock_num,
    "future_stock_num": stock_snapshot.c.future_stock_num,
    "total_occupied_stock_num": stock_snapshot.c.total_occupied_stock_num,
    "total_unoccupied_stock_num": stock_snapshot.c.total_unoccupied_stock_num,
    # 与界面徽标一致：正常 → 预警 → 售罄（预警优先于售罄，见前端 stockBadge）
    "status": sa.case(
        (stock_snapshot.c.is_alarming == 1, 1),
        (stock_snapshot.c.total_stock_num == 0, 2),
        else_=0,
    ),
    "synced_at": stock_snapshot.c.synced_at,
}


def list_stock(
    conn: sa.Connection, shop_ids: Sequence[int], *, alarm_only: bool = False,
    page: int = 1, page_size: int = 50, sort: str | None = None, order: SortOrder = "asc",
    quick: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """库存行左连商品快照取名称（stock_snapshot 无名称列）。
    默认按总库存升序（缺货的在前，未知库存排最后）。"""
    if not shop_ids:
        return [], 0
    conds: list[Any] = [stock_snapshot.c.shop_id.in_(list(shop_ids))]
    if alarm_only or quick == "alarm":
        conds.append(stock_snapshot.c.is_alarming == 1)
    if quick == "sold_out":  # 与汇总的「售罄」同口径：总库存为 0
        conds.append(stock_snapshot.c.total_stock_num == 0)
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
        .order_by(*order_by(
            STOCK_SORTS, sort or "total_stock_num", order if sort else "asc", (),
            stock_snapshot.c.id,
        ))
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
