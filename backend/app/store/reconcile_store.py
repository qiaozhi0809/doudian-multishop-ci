"""order_fact / reconcile_run / reconcile_findings 读写。

比较逻辑在 domain/reconcile_rules，事务与批次编排在 service/reconcile。
G.4 的「同一事务内先读旧快照再统一 upsert」由 service 用同一个 engine.begin() 包住
read_facts → insert_findings → upsert_facts 保证。
"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.domain.models import OrderFactDTO
from app.domain.reconcile_rules import FINDING_KINDS, Finding
from app.store.reconcile_schema import order_fact, reconcile_findings, reconcile_run
from app.store.sorting import SortOrder, order_by, rank_of, shop_name_of

_CHUNK_ROWS = 200
_CHUNK_IDS = 900  # SQLite 参数上限（旧版本 999）以内；一窗几千单时分批读写


def _chunks(items: Sequence, size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


_FACT_UPDATABLE = (
    "platform_status", "user_id", "pay_time", "biz_date", "pay_amount_cents",
    "goods_amount_cents", "promotion_cents", "post_cents", "receive_amount_cents",
    "exp_ship_time", "ship_time", "tracking_no", "company_code", "raw_json", "synced_at",
)


def read_facts(
    conn: sa.Connection, shop_id: int, order_nos: Sequence[str],
) -> dict[str, dict[str, Any]]:
    if not order_nos:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(list(order_nos), _CHUNK_IDS):
        rows = conn.execute(
            sa.select(order_fact).where(
                order_fact.c.shop_id == shop_id,
                order_fact.c.shop_order_id.in_(chunk),
            )
        ).mappings()
        out.update({r["shop_order_id"]: dict(r) for r in rows})
    return out


def upsert_facts(
    conn: sa.Connection, shop_id: int, facts: Sequence[OrderFactDTO], now: str,
) -> None:
    """统一 upsert；`first_seen_at` 只在首次插入时写入，冲突时不更新（G.4）。"""
    if not facts:
        return
    values = [
        {
            "shop_id": shop_id, "shop_order_id": f.order_no,
            "platform_status": f.platform_status, "user_id": f.user_id,
            "pay_time": f.pay_time, "biz_date": f.biz_date,
            "pay_amount_cents": f.pay_amount_cents,
            "goods_amount_cents": f.goods_amount_cents,
            "promotion_cents": f.promotion_cents, "post_cents": f.post_cents,
            "receive_amount_cents": f.receive_amount_cents,
            "exp_ship_time": f.exp_ship_time, "ship_time": f.ship_time,
            "tracking_no": f.tracking_no, "company_code": f.company_code,
            "raw_json": json.dumps(f.raw, ensure_ascii=False),
            "first_seen_at": now, "synced_at": now,
        }
        for f in facts
    ]
    for chunk in _chunks(values, _CHUNK_ROWS):
        stmt = sqlite_insert(order_fact).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["shop_id", "shop_order_id"],
            set_={col: stmt.excluded[col] for col in _FACT_UPDATABLE},
        )
        conn.execute(stmt)


def insert_findings(
    conn: sa.Connection, run_id: str, shop_id: int,
    findings: Sequence[tuple[str, Finding]], now: str,
) -> None:
    """findings: (shop_order_id, Finding)。"""
    if not findings:
        return
    rows = [
        {
            "run_id": run_id, "shop_id": shop_id, "shop_order_id": order_no,
            "kind": f.kind, "local_status": f.local_status,
            "platform_status": f.platform_status,
            "local_tracking_no": f.local_tracking_no,
            "platform_tracking_no": f.platform_tracking_no,
            "local_company_code": f.local_company_code,
            "platform_company_code": f.platform_company_code,
            "detail": f.detail, "status": "open", "created_at": now,
        }
        for order_no, f in findings
    ]
    for chunk in _chunks(rows, _CHUNK_ROWS):
        conn.execute(sa.insert(reconcile_findings), chunk)


FINDING_SORTS: dict[str, Any] = {
    "shop_name": shop_name_of(reconcile_findings.c.shop_id),
    # 按界面顺序：异常类型按定义顺序，处理状态 未处理 → 已处理
    "kind": rank_of(reconcile_findings.c.kind, FINDING_KINDS),
    "created_at": reconcile_findings.c.created_at,
    "status": rank_of(reconcile_findings.c.status, ("open", "handled")),
}


def list_findings(
    conn: sa.Connection, shop_ids: Sequence[int] | None, run_id: str | None,
    kind: str | None, status: str | None, page: int, page_size: int,
    sort: str | None = None, order: SortOrder = "asc",
) -> tuple[list[dict[str, Any]], int]:
    """默认按发现顺序倒序（最新的在前）。"""
    if shop_ids is not None and len(shop_ids) == 0:
        return [], 0
    cond = []
    if run_id is not None:
        cond.append(reconcile_findings.c.run_id == run_id)
    if shop_ids is not None:
        cond.append(reconcile_findings.c.shop_id.in_(shop_ids))
    if kind is not None:
        cond.append(reconcile_findings.c.kind == kind)
    if status is not None:
        cond.append(reconcile_findings.c.status == status)
    total = conn.execute(
        sa.select(sa.func.count()).select_from(reconcile_findings).where(*cond)
    ).scalar_one()
    rows = conn.execute(
        sa.select(reconcile_findings).where(*cond)
        .order_by(*order_by(FINDING_SORTS, sort, order, (reconcile_findings.c.id.desc(),),
                            reconcile_findings.c.id))
        .limit(page_size).offset((page - 1) * page_size)
    ).mappings()
    return [dict(r) for r in rows], int(total)


def get_finding(conn: sa.Connection, finding_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        sa.select(reconcile_findings).where(reconcile_findings.c.id == finding_id)
    ).mappings().first()
    return dict(row) if row else None


def mark_finding(
    conn: sa.Connection, finding_id: int, status: str, now: str,
) -> bool:
    result = conn.execute(
        sa.update(reconcile_findings).where(reconcile_findings.c.id == finding_id)
        .values(status=status, handled_at=now if status == "handled" else None)
    )
    return result.rowcount > 0


# ---- 对账批次 ----


def create_run(
    conn: sa.Connection, run_id: str, shop_ids: Sequence[int], window_days: int, now: str,
) -> None:
    conn.execute(sa.insert(reconcile_run).values(
        run_id=run_id, status="running", shop_ids=json.dumps(list(shop_ids)),
        window_days=window_days, started_at=now, scanned=0, finding_count=0,
    ))


def finish_run(
    conn: sa.Connection, run_id: str, status: str, scanned: int, finding_count: int,
    error: str | None, now: str,
) -> None:
    conn.execute(
        sa.update(reconcile_run).where(reconcile_run.c.run_id == run_id).values(
            status=status, scanned=scanned, finding_count=finding_count,
            error=error, finished_at=now,
        )
    )


def get_run(conn: sa.Connection, run_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        sa.select(reconcile_run).where(reconcile_run.c.run_id == run_id)
    ).mappings().first()
    return dict(row) if row else None


def latest_run(conn: sa.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        sa.select(reconcile_run).order_by(reconcile_run.c.id.desc()).limit(1)
    ).mappings().first()
    return dict(row) if row else None
