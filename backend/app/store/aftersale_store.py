"""aftersale 读写（售后聚合，附录 E）。detail_json 保存平台原始报文，展示字段由 adapter 提取。"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

import sqlalchemy as sa

from app.domain.aggregate_models import AftersaleDTO
from app.store.aggregate_schema import aftersale
from app.store.sorting import SortOrder, order_by, shop_name_of

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


# 计数卡快捷筛选：pending 待办（仍在流转）/ audit 待审核（有审核类操作按钮）/
# due_soon 临近超时（24 小时内到处理截止时间，含已超时未完结的）
AFTERSALE_QUICK_FILTERS = ("pending", "audit", "due_soon")

_OPEN = aftersale.c.status_deadline.is_not(None)


def _audit_button() -> Any:
    """报文 buttons 里有 *_audit（如 refund_audit「同意退款」）= 等商家审核。平台未公开数字状态，
    按可用操作判断，不猜测状态码。"""
    buttons = sa.func.json_each(aftersale.c.detail_json, "$.buttons").table_valued("value")
    return sa.exists(
        sa.select(1).select_from(buttons)
        .where(sa.func.json_extract(buttons.c.value, "$.button").like("%\\_audit", escape="\\"))
    )


def _quick_cond(quick: str, due_before: str) -> Any:
    if quick == "pending":
        return _OPEN
    if quick == "audit":
        return sa.and_(_OPEN, _audit_button())
    if quick == "due_soon":
        return sa.and_(_OPEN, aftersale.c.status_deadline < due_before)
    raise ValueError(f"未知的售后快捷筛选: {quick}")


def _conds(
    shop_ids: Sequence[int], status: int | None, open_only: bool, keyword: str | None,
    quick: str | None = None, due_before: str = "",
) -> list[Any]:
    conds: list[Any] = [aftersale.c.shop_id.in_(list(shop_ids))]
    if quick is not None:
        conds.append(_quick_cond(quick, due_before))
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


def _label(text_key: str, code: Any, prefix: str) -> Any:
    """界面显示的文案：平台下发的成品文案，缺省时「状态 13」这类兜底（与前端 statusLabel 一致）。
    数字枚举取值未公开、无法定义顺序，所以状态 / 类型列按显示文案排，同名的排在一起。"""
    return sa.func.coalesce(
        sa.func.json_extract(aftersale.c.detail_json, f"$.text_part.{text_key}"),
        sa.case((code.is_(None), None), else_=sa.literal(prefix) + sa.cast(code, sa.Text)),
    )


AFTERSALE_SORTS: dict[str, Any] = {
    "shop_name": shop_name_of(aftersale.c.shop_id),
    "type": _label("after_sale_type_text", aftersale.c.type, "类型 "),
    "status": _label("after_sale_status_text", aftersale.c.status, "状态 "),
    "refund_amount_cents": aftersale.c.refund_amount_cents,
    "apply_time": aftersale.c.apply_time,
    "status_deadline": aftersale.c.status_deadline,
}


def list_aftersales(
    conn: sa.Connection, shop_ids: Sequence[int], *, status: int | None = None,
    open_only: bool = False, keyword: str | None = None, by_deadline: bool = False,
    page: int = 1, page_size: int = 50, sort: str | None = None, order: SortOrder = "asc",
    quick: str | None = None, due_before: str = "",
) -> tuple[list[dict[str, Any]], int]:
    """本地列表；默认排序：`by_deadline`（待办队列）按处理截止时间升序、已完结的排最后，
    否则按申请时间倒序。指定 sort 时按白名单字段排序。due_before 供 quick=due_soon 使用。"""
    if not shop_ids:
        return [], 0
    conds = _conds(shop_ids, status, open_only, keyword, quick, due_before)
    total = conn.execute(
        sa.select(sa.func.count()).select_from(aftersale).where(*conds)
    ).scalar_one()
    default = (
        (aftersale.c.status_deadline.is_(None), aftersale.c.status_deadline.asc(),
         aftersale.c.id.asc())
        if by_deadline else
        (aftersale.c.apply_time.desc(), aftersale.c.id.desc())
    )
    rows = conn.execute(
        sa.select(aftersale).where(*conds)
        .order_by(*order_by(AFTERSALE_SORTS, sort, order, default, aftersale.c.id))
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
