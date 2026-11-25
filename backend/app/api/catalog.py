"""商品 / 库存聚合接口（只读）。"""

from fastapi import APIRouter, Depends, Query, Request

from app.api.catalog_schemas import (
    ProductCountsResponse,
    ProductGroupsResponse,
    ProductPage,
    ProductSyncResponse,
    ShopGroups,
    ShopProductCounts,
    ShopProductSync,
    ShopStockSync,
    ShopWarehouses,
    StockPage,
    StockSummary,
    StockSyncResponse,
    WarehousesResponse,
)
from app.api.deps import require_admin
from app.api.params import parse_shop_ids

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


async def _target_ids(request: Request, shop_ids: str | None) -> list[int]:
    """显式指定的店铺先预检；不指定则只跑可用店铺（与订单同步一致）。"""
    state = request.app.state
    explicit = parse_shop_ids(shop_ids)
    ids = state.shop_admin.target_ids(explicit)
    if explicit is not None:
        for shop_id in ids:
            await state.runner.precheck(shop_id)
        return ids
    return state.shop_admin.runnable_ids(ids)


@router.get("/products", response_model=ProductPage)
def list_products(
    request: Request, shop_ids: str | None = None, tab: str | None = None,
    keyword: str | None = None, page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> ProductPage:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    rows, total = state.catalog.list_products(
        ids, tab=tab, keyword=keyword, page=page, page_size=page_size
    )
    return ProductPage(items=rows, total=total, page=page, page_size=page_size)


@router.get("/products/counts", response_model=ProductCountsResponse)
async def product_counts(
    request: Request, shop_ids: str | None = None, admin: str = Depends(require_admin)
) -> ProductCountsResponse:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    results = await state.catalog.product_counts(ids, admin)
    return ProductCountsResponse(shops=[
        ShopProductCounts(
            shop_id=r.shop_id, source=r.source, counts=r.counts,
            error=r.error, fetched_at=r.fetched_at,
        )
        for r in results
    ])


@router.get("/products/groups", response_model=ProductGroupsResponse)
async def product_groups(
    request: Request, shop_ids: str | None = None, admin: str = Depends(require_admin)
) -> ProductGroupsResponse:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    results = await state.catalog.product_groups(ids, admin)
    return ProductGroupsResponse(shops=[
        ShopGroups(
            shop_id=r.shop_id, source=r.source, items=r.items,
            error=r.error, fetched_at=r.fetched_at,
        )
        for r in results
    ])


@router.post("/products/sync", response_model=ProductSyncResponse)
async def sync_products(
    request: Request, shop_ids: str | None = None, admin: str = Depends(require_admin)
) -> ProductSyncResponse:
    ids = await _target_ids(request, shop_ids)
    results = await request.app.state.catalog.sync_products(ids, admin)
    return ProductSyncResponse(shops=[
        ShopProductSync(
            shop_id=r.shop_id, fetched=r.fetched, complete=r.complete,
            error=r.error, synced_at=r.synced_at,
        )
        for r in results
    ])


@router.get("/stock", response_model=StockPage)
def list_stock(
    request: Request, shop_ids: str | None = None, alarm_only: bool = False,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
) -> StockPage:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    rows, total = state.catalog.list_stock(
        ids, alarm_only=alarm_only, page=page, page_size=page_size
    )
    return StockPage(items=rows, total=total, page=page, page_size=page_size)


@router.get("/stock/summary", response_model=StockSummary)
def stock_summary(request: Request, shop_ids: str | None = None) -> StockSummary:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    return StockSummary(**state.catalog.stock_summary(ids))


@router.get("/stock/warehouses", response_model=WarehousesResponse)
async def warehouses(
    request: Request, shop_ids: str | None = None, admin: str = Depends(require_admin)
) -> WarehousesResponse:
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    results = await state.catalog.warehouses(ids, admin)
    return WarehousesResponse(shops=[
        ShopWarehouses(
            shop_id=r.shop_id, source=r.source, items=r.items,
            error=r.error, fetched_at=r.fetched_at,
        )
        for r in results
    ])


@router.post("/stock/sync", response_model=StockSyncResponse)
async def sync_stock(
    request: Request, shop_ids: str | None = None, admin: str = Depends(require_admin)
) -> StockSyncResponse:
    ids = await _target_ids(request, shop_ids)
    results = await request.app.state.catalog.sync_stock(ids, admin)
    return StockSyncResponse(shops=[
        ShopStockSync(
            shop_id=r.shop_id, fetched=r.fetched, complete=r.complete,
            alarm_count=r.alarm_count, sold_out_count=r.sold_out_count,
            error=r.error, synced_at=r.synced_at,
        )
        for r in results
    ])
