"""发货接口：待发货订单池、发货前检查、提交发货、批次结果（flows 7.5）。"""

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import require_admin
from app.api.params import parse_shop_ids
from app.api.shipping_schemas import (
    BlockedShipOut,
    ShipBatchResponse,
    ShipCheckRequest,
    ShipCheckResponse,
    ShipmentRow,
    ShipPoolPage,
    ShipPoolRow,
    ShipRequest,
    ShipStartedOut,
    ShopCheckErrorOut,
    ShopCheckOut,
)

router = APIRouter(prefix="/api/shipping", tags=["shipping"])


def _check_response(request: Request, view) -> ShipCheckResponse:
    return ShipCheckResponse(
        shops=[
            ShopCheckOut(
                shop_id=s.shop_id, shop_name=s.shop_name, order_nos=list(s.order_nos),
                total=s.result.total, double_check_num=s.result.double_check_num,
                double_check_detail=list(s.result.double_check_detail),
                without_aftersale=list(s.result.without_aftersale),
                place_holder=s.result.place_holder,
            )
            for s in view.shops
        ],
        blocked=[BlockedShipOut(
            order_id=b.order_id, order_no=b.order_no, shop_name=b.shop_name,
            reason=b.reason) for b in view.blocked],
        shop_errors=[ShopCheckErrorOut(
            shop_id=e.shop_id, shop_name=e.shop_name, reason=e.reason)
            for e in view.shop_errors],
        total_orders=len(view.targets),
        double_check_total=view.double_check_total,
        dry_run=request.app.state.settings.dry_run,
    )


@router.get("/pool", response_model=ShipPoolPage)
def pool(
    request: Request,
    shop_ids: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> ShipPoolPage:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    rows, total = state.shipping.pool(ids, page, page_size)
    return ShipPoolPage(
        items=[ShipPoolRow(**r) for r in rows], total=total, page=page, page_size=page_size)


@router.post("/check", response_model=ShipCheckResponse)
async def check(
    request: Request, payload: ShipCheckRequest, admin: str = Depends(require_admin)
) -> ShipCheckResponse:
    view = await request.app.state.shipping.check(payload.order_ids, admin)
    return _check_response(request, view)


@router.post("/ship", response_model=ShipStartedOut, status_code=202)
async def ship(
    request: Request, payload: ShipRequest, admin: str = Depends(require_admin)
) -> ShipStartedOut:
    started = await request.app.state.shipping.ship(
        payload.order_ids, admin, payload.double_check_ack)
    return ShipStartedOut(
        batch_id=started.batch_id, shop_ids=started.shop_ids,
        package_count=started.package_count, order_count=started.order_count,
    )


@router.get("/batches/{batch_id}", response_model=ShipBatchResponse)
def batch(request: Request, batch_id: str) -> ShipBatchResponse:
    rows = request.app.state.shipping.batch(batch_id)
    return ShipBatchResponse(
        batch_id=batch_id,
        ok=sum(1 for r in rows if r["status"] == "success"),
        failed=sum(1 for r in rows if r["status"] == "failed"),
        pending=sum(1 for r in rows if r["status"] == "pending"),
        items=[ShipmentRow(**r) for r in rows],
    )
