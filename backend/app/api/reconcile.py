"""对账接口：手动触发、结果查询、标记已处理（backend 5.8 / flows 7.6）。"""

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import require_admin
from app.api.params import parse_shop_ids
from app.api.reconcile_schemas import (
    ReconcileFindingRow,
    ReconcileFindingsPage,
    ReconcileMarkRequest,
    ReconcileRunRequest,
    ReconcileRunRow,
    ReconcileStarted,
)

router = APIRouter(prefix="/api/reconcile", tags=["reconcile"])


def _run_row(run: dict | None) -> ReconcileRunRow | None:
    return None if run is None else ReconcileRunRow(**run)


@router.post("/run", response_model=ReconcileStarted, status_code=202)
async def run(
    request: Request,
    payload: ReconcileRunRequest | None = None,
    shop_ids: str | None = None,
    admin: str = Depends(require_admin),
) -> ReconcileStarted:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    started = await state.reconcile.run(
        ids, admin, payload.window_days if payload else None)
    return ReconcileStarted(**started)


@router.get("/findings", response_model=ReconcileFindingsPage)
def findings(
    request: Request,
    shop_ids: str | None = None,
    run_id: str | None = None,
    kind: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> ReconcileFindingsPage:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    rows, total, run_row = state.reconcile.findings(
        ids, run_id, kind, status, page, page_size)
    return ReconcileFindingsPage(
        items=[ReconcileFindingRow(**r) for r in rows], total=total,
        page=page, page_size=page_size, run=_run_row(run_row),
    )


@router.patch("/findings/{finding_id}", response_model=ReconcileFindingRow)
def mark_finding(
    request: Request, finding_id: int, payload: ReconcileMarkRequest,
    admin: str = Depends(require_admin),
) -> ReconcileFindingRow:
    row = request.app.state.reconcile.mark(finding_id, payload.status)
    return ReconcileFindingRow(**row)
