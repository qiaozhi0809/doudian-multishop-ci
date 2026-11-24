"""订单接口：本地库列表、tab 计数、手动同步。"""

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import require_admin
from app.api.order_schemas import (
    LocalStatus,
    OrderCounts,
    OrderCountsResponse,
    OrderPage,
    OrderRow,
    ShopOrderCounts,
    SyncStarted,
)
from app.api.params import parse_shop_ids
from app.domain.order_status import LocalOrderStatus
from app.service.background import TaskAlreadyRunning

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("", response_model=OrderPage)
def list_orders(
    request: Request,
    shop_ids: str | None = None,
    status: LocalStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> OrderPage:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    rows, total = state.order_query.list_orders(
        ids, LocalOrderStatus(status) if status else None, page, page_size
    )
    return OrderPage(items=[OrderRow(**r) for r in rows], total=total, page=page,
                     page_size=page_size)


@router.get("/counts", response_model=OrderCountsResponse)
async def order_counts(
    request: Request, shop_ids: str | None = None, admin: str = Depends(require_admin)
) -> OrderCountsResponse:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    results = await state.order_query.counts(ids, admin)
    return OrderCountsResponse(shops=[
        ShopOrderCounts(
            shop_id=r.shop_id, source=r.source, error=r.error,  # type: ignore[arg-type]
            counts=OrderCounts(**r.counts) if r.counts else None,
        )
        for r in results
    ])


@router.post("/sync", response_model=SyncStarted, status_code=202)
async def sync_orders(
    request: Request, shop_ids: str | None = None, admin: str = Depends(require_admin)
) -> SyncStarted:
    """显式指定的店铺先同步预检（暂停 / 出口 / 会话不通即报错）；不指定则只跑可用店铺。"""
    state = request.app.state
    explicit = parse_shop_ids(shop_ids)
    ids = state.shop_admin.target_ids(explicit)
    if explicit is not None:
        for shop_id in ids:
            await state.runner.precheck(shop_id)
    else:
        ids = state.shop_admin.runnable_ids(ids)
    started, running = [], []
    for shop_id in ids:
        try:
            state.tasks.spawn(f"orders-{shop_id}", state.order_sync.sync_pending(shop_id, admin))
            started.append(shop_id)
        except TaskAlreadyRunning:
            running.append(shop_id)
    return SyncStarted(started=started, already_running=running)
