"""打单台接口：订单池、两步提交（取号 / 打单并发货 / 作废）。"""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import require_admin
from app.api.label_schemas import (
    ExecuteRequest,
    ExecuteStarted,
    LabelOrderRow,
    LabelPoolPage,
    LabelPreviewResponse,
    PreviewRequest,
    VoidPreviewRequest,
    VoidPreviewResponse,
)
from app.api.list_sort import LabelPoolSort, SortOrder
from app.api.params import parse_shop_ids
from app.service.label_preview import MODE_FETCH_AND_SHIP, MODE_OBTAIN, MODE_VOID

router = APIRouter(prefix="/api/labels", tags=["labels"])


def _preview_response(state, record) -> dict:
    return state.label_preview.view(record)


@router.get("/pool", response_model=LabelPoolPage)
def pool(
    request: Request,
    shop_ids: str | None = None,
    stage: Literal["pending", "labeled"] = "pending",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sort: LabelPoolSort | None = None,
    order: SortOrder = "asc",
) -> LabelPoolPage:
    """默认按支付时间从早到晚；sort 指定白名单字段时按该字段排序后再分页。"""
    state = request.app.state
    ids = state.shop_admin.target_ids(parse_shop_ids(shop_ids))
    rows, total = state.label_pool.list(ids, stage, page, page_size, sort, order)
    return LabelPoolPage(
        items=[LabelOrderRow(**r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.post("/preview", response_model=LabelPreviewResponse)
def preview_obtain(
    request: Request, payload: PreviewRequest, admin: str = Depends(require_admin)
) -> LabelPreviewResponse:
    record = request.app.state.label_preview.preview_obtain(
        payload.order_ids, payload.courier_by_shop or {}, actor=admin, mode=MODE_OBTAIN)
    return LabelPreviewResponse(**_preview_response(request.app.state, record))


@router.post("/fetch-and-ship/preview", response_model=LabelPreviewResponse)
def preview_fetch_and_ship(
    request: Request, payload: PreviewRequest, admin: str = Depends(require_admin)
) -> LabelPreviewResponse:
    record = request.app.state.label_preview.preview_obtain(
        payload.order_ids, payload.courier_by_shop or {}, actor=admin,
        mode=MODE_FETCH_AND_SHIP)
    return LabelPreviewResponse(**_preview_response(request.app.state, record))


@router.post("/void/preview", response_model=VoidPreviewResponse)
def preview_void(
    request: Request, payload: VoidPreviewRequest, admin: str = Depends(require_admin)
) -> VoidPreviewResponse:
    record = request.app.state.label_preview.preview_void(payload.order_ids, actor=admin)
    return VoidPreviewResponse(**_preview_response(request.app.state, record))


@router.post("/execute", response_model=ExecuteStarted, status_code=202)
async def execute_obtain(
    request: Request, payload: ExecuteRequest, admin: str = Depends(require_admin)
) -> ExecuteStarted:
    started = request.app.state.labeling.execute(
        payload.preview_id, admin, expected_mode=MODE_OBTAIN)
    return ExecuteStarted(**vars(started))


@router.post("/fetch-and-ship/execute", response_model=ExecuteStarted, status_code=202)
async def execute_fetch_and_ship(
    request: Request, payload: ExecuteRequest, admin: str = Depends(require_admin)
) -> ExecuteStarted:
    started = request.app.state.labeling.execute(
        payload.preview_id, admin, expected_mode=MODE_FETCH_AND_SHIP)
    return ExecuteStarted(**vars(started))


@router.post("/void/execute", response_model=ExecuteStarted, status_code=202)
async def execute_void(
    request: Request, payload: ExecuteRequest, admin: str = Depends(require_admin)
) -> ExecuteStarted:
    started = request.app.state.labeling.execute(
        payload.preview_id, admin, expected_mode=MODE_VOID)
    return ExecuteStarted(**vars(started))
