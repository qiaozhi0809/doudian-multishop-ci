"""售后聚合接口（只读）：本地列表 / 待办队列 / 状态计数 / 详情 / 同步。"""

from fastapi import APIRouter, Depends, Query, Request

from app.api.aftersale_schemas import (
    AftersaleCountsResponse,
    AftersaleDetail,
    AftersalePage,
    AftersaleStatusesResponse,
    AftersaleSyncResponse,
    ShopAftersaleCounts,
    ShopAftersaleSync,
)
from app.api.deps import require_admin
from app.api.params import parse_shop_ids

router = APIRouter(prefix="/api/aftersale", tags=["aftersale"])


def _page(rows: list[dict], total: int, page: int, page_size: int) -> AftersalePage:
    return AftersalePage(items=rows, total=total, page=page, page_size=page_size)


@router.get("", response_model=AftersalePage)
def list_aftersale(
    request: Request, shop_ids: str | None = None, status: int | None = None,
    pending: bool = False, keyword: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
) -> AftersalePage:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    rows, total = state.aftersale.list_local(
        ids, status=status, open_only=pending, keyword=keyword,
        page=page, page_size=page_size,
    )
    return _page(rows, total, page, page_size)


@router.get("/todo", response_model=AftersalePage)
def list_todo(
    request: Request, shop_ids: str | None = None,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
) -> AftersalePage:
    """跨店待办队列：仍在流转（有处理截止时间）的售后单，按截止时间升序。"""
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    rows, total = state.aftersale.list_local(
        ids, open_only=True, by_deadline=True, page=page, page_size=page_size
    )
    return _page(rows, total, page, page_size)


@router.get("/statuses", response_model=AftersaleStatusesResponse)
def list_statuses(request: Request, shop_ids: str | None = None) -> AftersaleStatusesResponse:
    """筛选下拉用：本地出现过的状态 + 平台文案。"""
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    return AftersaleStatusesResponse(items=state.aftersale.statuses(ids))


@router.get("/counts", response_model=AftersaleCountsResponse)
async def aftersale_counts(
    request: Request, shop_ids: str | None = None, admin: str = Depends(require_admin)
) -> AftersaleCountsResponse:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    results = await state.aftersale.counts(ids, admin)
    return AftersaleCountsResponse(shops=[
        ShopAftersaleCounts(
            shop_id=r.shop_id, source=r.source, counts=r.counts,
            pending_total=r.pending_total, error=r.error, fetched_at=r.fetched_at,
        )
        for r in results
    ])


@router.post("/sync", response_model=AftersaleSyncResponse)
async def sync_aftersale(
    request: Request, shop_ids: str | None = None, admin: str = Depends(require_admin)
) -> AftersaleSyncResponse:
    """显式指定的店铺先预检（暂停 / 出口 / 会话不通即报错）；不指定则只跑可用店铺。"""
    state = request.app.state
    explicit = parse_shop_ids(shop_ids)
    ids = state.shop_admin.target_ids(explicit)
    if explicit is not None:
        for shop_id in ids:
            await state.runner.precheck(shop_id)
    else:
        ids = state.shop_admin.runnable_ids(ids)
    results = await state.aftersale.sync(ids, admin)
    return AftersaleSyncResponse(shops=[
        ShopAftersaleSync(
            shop_id=r.shop_id, fetched=r.fetched, complete=r.complete,
            error=r.error, synced_at=r.synced_at,
        )
        for r in results
    ])


@router.get("/{after_sale_id}", response_model=AftersaleDetail)
async def aftersale_detail(
    request: Request, after_sale_id: str, shop_id: int, admin: str = Depends(require_admin)
) -> AftersaleDetail:
    detail = await request.app.state.aftersale.detail(shop_id, after_sale_id, admin)
    return AftersaleDetail(shop_id=shop_id, after_sale_id=after_sale_id, detail=detail)
