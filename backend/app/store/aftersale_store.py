"""aftersale 读写（售后聚合，附录 E）。detail_json 保存平台原始报文，展示字段由 adapter 提取。"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

import sqlalchemy as sa

from app.domain.aggregate_models import AftersaleDTO
from app.store.aggregate_schema import aftersale

OPEN_ONLY = "open_only"


def upsert_aftersales(
    conn: sa.Connection, shop_id: int, items: Sequence[AftersaleDTO], now: str
) -> int:
    for a in items:
        values = {
            "order_no": a.order_no, "type": a.type, "status": a.status,
            "refund_amount_cents": a.refund_amount_cents,
            "status_deadline": a.status_deadline, "apply_time": a.apply_time,
            "detail_json": json.dumps(a.raw, ensure_ascii=False), "synced_at": now,
        }
        row_id = conn.execute(
            sa.select(aftersale.c.id).where(
                aftersale.c.shop_id == shop_id, aftersale.c.after_sale_id == a.after_sale_id
            )
        ).scalar()
        if row_id is None:
            conn.execute(sa.insert(aftersale).values(
                shop_id=shop_id, after_sale_id=a.after_sale_id, **values
            ))
        else:
            conn.execute(sa.update(aftersale).where(aftersale.c.id == row_id).values(**values))
    return len(items)


def prune_unseen(conn: sa.Connection, shop_id: int, now: str) -> int:
    """完整同步后调用：本次没出现的售后单（同店）删除。未同步到的行 synced_at 不是本次时间。"""
    result = conn.execute(
        sa.delete(aftersale).where(
            aftersale.c.shop_id == shop_id, aftersale.c.synced_at != now
        )
    )
    return result.rowcount or 0


def _conds(
    shop_ids: Sequence[int], status: int | None, open_only: bool, keyword: str | None,
) -> list[Any]:
    conds: list[Any] = [aftersale.c.shop_id.in_(list(shop_ids))]
    if status is not None:
        conds.append(aftersale.c.status == status)
    if open_only:
        conds.append(aftersale.c.status_deadline.is_not(None))
    if keyword:
        like = f"%{keyword}%"
        conds.append(sa.or_(
            aftersale.c.order_no.like(like), aftersale.c.after_sale_id.like(like)
        ))
    return conds


def list_aftersales(
    conn: sa.Connection, shop_ids: Sequence[int], *, status: int | None = None,
    open_only: bool = False, keyword: str | None = None, by_deadline: bool = False,
    page: int = 1, page_size: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    """本地列表；`by_deadline` 用于待办队列（处理截止时间升序，已完结的排最后）。"""
    if not shop_ids:
        return [], 0
    conds = _conds(shop_ids, status, open_only, keyword)
    total = conn.execute(
        sa.select(sa.func.count()).select_from(aftersale).where(*conds)
    ).scalar_one()
    order = (
        (aftersale.c.status_deadline.is_(None), aftersale.c.status_deadline.asc())
        if by_deadline else
        (aftersale.c.apply_time.desc(), aftersale.c.id.desc())
    )
    rows = conn.execute(
        sa.select(aftersale).where(*conds).order_by(*order)
        .limit(page_size).offset((page - 1) * page_size)
    ).mappings().all()
    return [dict(r) for r in rows], int(total)


def latest_synced_at(conn: sa.Connection, shop_ids: Sequence[int]) -> dict[int, str]:
    if not shop_ids:
        return {}
    rows = conn.execute(
        sa.select(aftersale.c.shop_id, sa.func.max(aftersale.c.synced_at))
        .where(aftersale.c.shop_id.in_(list(shop_ids)))
        .group_by(aftersale.c.shop_id)
    )
    return {r[0]: r[1] for r in rows}


def display_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """数据库行 → 接口行（detail_json 解析留给 service 调 adapter 提取）。"""
    detail: dict = {}
    if row.get("detail_json"):
        try:
            parsed = json.loads(row["detail_json"])
            detail = parsed if isinstance(parsed, dict) else {}
        except ValueError:
            detail = {}
    return {
        "id": row["id"], "shop_id": row["shop_id"], "after_sale_id": row["after_sale_id"],
        "order_no": row["order_no"], "type": row["type"], "status": row["status"],
        "refund_amount_cents": row["refund_amount_cents"],
        "status_deadline": row["status_deadline"], "apply_time": row["apply_time"],
        "synced_at": row["synced_at"], "detail": detail,
    }


def list_statuses(
    conn: sa.Connection, shop_ids: Sequence[int]
) -> list[tuple[int, str | None]]:
    """本地出现过的数字状态 + 一条样本报文（用于提取平台状态文案做筛选项）。"""
    if not shop_ids:
        return []
    rows = conn.execute(
        sa.select(aftersale.c.status, sa.func.min(aftersale.c.detail_json))
        .where(aftersale.c.shop_id.in_(list(shop_ids)), aftersale.c.status.is_not(None))
        .group_by(aftersale.c.status)
        .order_by(aftersale.c.status)
    )
    return [(int(r[0]), r[1]) for r in rows]
