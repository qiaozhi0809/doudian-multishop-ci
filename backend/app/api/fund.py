"""资金聚合接口（只读）：概览 / 待结算 / 保证金 / 账单 / 同步。"""

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import require_admin
from app.api.fund_schemas import (
    BillsResponse,
    FundSummary,
    FundSyncResponse,
    MarginResponse,
    ShopBills,
    ShopFundSync,
    UnsettledPage,
)
from app.api.params import parse_shop_ids
from app.service.fund import DEFAULT_BILL_DAYS

router = APIRouter(prefix="/api/fund", tags=["fund"])


@router.get("/summary", response_model=FundSummary)
def fund_summary(request: Request, shop_ids: str | None = None) -> FundSummary:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    return FundSummary(**state.fund.summary(ids))


@router.get("/unsettled", response_model=UnsettledPage)
def list_unsettled(
    request: Request, shop_ids: str | None = None, page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> UnsettledPage:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    rows, total = state.fund.list_unsettled(ids, page, page_size)
    return UnsettledPage(items=rows, total=total, page=page, page_size=page_size)


@router.get("/margin", response_model=MarginResponse)
def list_margin(request: Request, shop_ids: str | None = None) -> MarginResponse:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    return MarginResponse(items=state.fund.list_margin(ids))


@router.get("/bills", response_model=BillsResponse)
async def list_bills(
    request: Request, shop_ids: str | None = None,
    days: int = Query(DEFAULT_BILL_DAYS, ge=1, le=90),
    page: int = Query(0, ge=0), admin: str = Depends(require_admin),
) -> BillsResponse:
    """上游账单（不落库）；新店通常为空。金额字段未校准时 amount_status=pending。"""
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    results = await state.fund.bills(ids, admin, days=days, page=page)
    return BillsResponse(days=days, shops=[
        ShopBills(
            shop_id=r.shop_id, source=r.source, total=r.total, items=r.items,
            error=r.error, fetched_at=r.fetched_at,
        )
        for r in results
    ])


@router.post("/sync", response_model=FundSyncResponse)
async def sync_fund(
    request: Request, shop_ids: str | None = None, admin: str = Depends(require_admin)
) -> FundSyncResponse:
    state = request.app.state
    explicit = parse_shop_ids(shop_ids)
    ids = state.shop_admin.target_ids(explicit)
    if explicit is not None:
        for shop_id in ids:
            await state.runner.precheck(shop_id)
    else:
        ids = state.shop_admin.runnable_ids(ids)
    results = await state.fund.sync(ids, admin)
    return FundSyncResponse(shops=[
        ShopFundSync(
            shop_id=r.shop_id, unsettled_count=r.unsettled_count,
            margin_synced=r.margin_synced, note=r.note, error=r.error, synced_at=r.synced_at,
        )
        for r in results
    ])
