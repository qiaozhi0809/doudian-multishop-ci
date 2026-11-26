"""fund_unsettled / margin_account 读写（资金聚合，附录 F）。

待结算是一份快照：每次同步按店整体替换（已结算的条目要从列表消失）。
"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa

from app.domain.aggregate_models import FundUnsettledDTO, MarginDTO
from app.store.aggregate_schema import fund_unsettled, margin_account
from app.store.sorting import SortOrder, order_by, shop_name_of


def replace_unsettled(
    conn: sa.Connection, shop_id: int, items: Sequence[FundUnsettledDTO], now: str
) -> int:
    conn.execute(sa.delete(fund_unsettled).where(fund_unsettled.c.shop_id == shop_id))
    if items:
        conn.execute(sa.insert(fund_unsettled), [
            {
                "shop_id": shop_id, "shop_order_no": u.shop_order_no,
                "sku_order_no": u.sku_order_no, "product_id": u.product_id,
                "income_amount_cents": u.income_amount_cents,
                "unsettled_amount_cents": u.unsettled_amount_cents,
                "platform_service_fee_cents": u.platform_service_fee_cents,
                "ecom_order_status": u.ecom_order_status,
                "expected_settle_time": u.expected_settle_time,
                "settle_period_detail": u.settle_period_detail,
                "raw_json": json.dumps(u.raw, ensure_ascii=False), "synced_at": now,
            }
            for u in items
        ])
    return len(items)


UNSETTLED_SORTS: dict[str, Any] = {
    "shop_name": shop_name_of(fund_unsettled.c.shop_id),
    "income_amount_cents": fund_unsettled.c.income_amount_cents,
    "platform_service_fee_cents": fund_unsettled.c.platform_service_fee_cents,
    "unsettled_amount_cents": fund_unsettled.c.unsettled_amount_cents,
    "ecom_order_status": fund_unsettled.c.ecom_order_status,
    "synced_at": fund_unsettled.c.synced_at,
}


def list_unsettled(
    conn: sa.Connection, shop_ids: Sequence[int], page: int = 1, page_size: int = 50,
    sort: str | None = None, order: SortOrder = "asc",
) -> tuple[list[dict[str, Any]], int]:
    """默认按入库顺序倒序（最近同步进来的在前）。"""
    if not shop_ids:
        return [], 0
    conds = [fund_unsettled.c.shop_id.in_(list(shop_ids))]
    total = conn.execute(
        sa.select(sa.func.count()).select_from(fund_unsettled).where(*conds)
    ).scalar_one()
    rows = conn.execute(
        sa.select(fund_unsettled).where(*conds)
        .order_by(*order_by(UNSETTLED_SORTS, sort, order, (fund_unsettled.c.id.desc(),),
                            fund_unsettled.c.id))
        .limit(page_size).offset((page - 1) * page_size)
    ).mappings().all()
    return [dict(r) for r in rows], int(total)


def unsettled_totals_by_shop(
    conn: sa.Connection, shop_ids: Sequence[int]
) -> dict[int, tuple[int, int]]:
    """{shop_id: (待结算金额合计（分）, 条数)}。"""
    if not shop_ids:
        return {}
    rows = conn.execute(
        sa.select(
            fund_unsettled.c.shop_id,
            sa.func.coalesce(sa.func.sum(fund_unsettled.c.unsettled_amount_cents), 0),
            sa.func.count(),
        ).where(fund_unsettled.c.shop_id.in_(list(shop_ids)))
        .group_by(fund_unsettled.c.shop_id)
    )
    return {r[0]: (int(r[1]), int(r[2])) for r in rows}


def latest_synced_at(conn: sa.Connection, shop_ids: Sequence[int]) -> dict[int, str]:
    if not shop_ids:
        return {}
    rows = conn.execute(
        sa.select(fund_unsettled.c.shop_id, sa.func.max(fund_unsettled.c.synced_at))
        .where(fund_unsettled.c.shop_id.in_(list(shop_ids)))
        .group_by(fund_unsettled.c.shop_id)
    )
    return {r[0]: r[1] for r in rows}


def upsert_margin(conn: sa.Connection, shop_id: int, margin: MarginDTO, now: str) -> None:
    values = {
        "payable_cents": margin.payable_cents, "balance_cents": margin.balance_cents,
        "basic_payable_cents": margin.basic_payable_cents,
        "basic_balance_cents": margin.basic_balance_cents,
        "withdrawable_cents": margin.withdrawable_cents, "level": margin.level,
        "raw_json": json.dumps(margin.raw, ensure_ascii=False), "synced_at": now,
    }
    row_id = conn.execute(
        sa.select(margin_account.c.id).where(margin_account.c.shop_id == shop_id)
    ).scalar()
    if row_id is None:
        conn.execute(sa.insert(margin_account).values(shop_id=shop_id, **values))
    else:
        conn.execute(
            sa.update(margin_account).where(margin_account.c.id == row_id).values(**values)
        )


def list_margin(conn: sa.Connection, shop_ids: Sequence[int]) -> list[dict[str, Any]]:
    if not shop_ids:
        return []
    rows = conn.execute(
        sa.select(margin_account).where(margin_account.c.shop_id.in_(list(shop_ids)))
        .order_by(margin_account.c.shop_id)
    ).mappings().all()
    return [dict(r) for r in rows]
