"""打单台接口的请求 / 响应模型。"""

from typing import Literal

from pydantic import BaseModel, Field

from app.api.order_schemas import OrderItem

MAX_BATCH = 200


class WaybillRow(BaseModel):
    id: int
    courier_code: str
    waybill_no: str | None
    status: str
    seq: int
    obtained_at: str | None
    template_code: str | None


class LabelOrderRow(BaseModel):
    id: int
    shop_id: int
    shop_name: str
    order_no: str
    status: str
    platform_status: int | None
    combine_id: str | None
    exception_reason: str | None
    amount_cents: int | None
    pay_time: str | None
    exp_ship_time: str | None
    items: list[OrderItem]
    blocked_reason: str | None
    waybill: WaybillRow | None


class LabelPoolPage(BaseModel):
    items: list[LabelOrderRow]
    total: int
    page: int
    page_size: int


class PreviewRequest(BaseModel):
    order_ids: list[int] = Field(min_length=1, max_length=MAX_BATCH)
    courier_by_shop: dict[str, str] | None = None


class VoidPreviewRequest(BaseModel):
    order_ids: list[int] = Field(min_length=1, max_length=MAX_BATCH)


class ExecuteRequest(BaseModel):
    preview_id: str


class PreviewShop(BaseModel):
    shop_id: int
    shop_name: str
    courier_code: str
    courier_name: str | None
    template_code: str
    ebill_id: str
    net_code: str
    account_balance: int | None
    ready_order_ids: list[int]


class VoidWaybill(BaseModel):
    waybill_id: int
    order_id: int
    order_no: str
    courier_code: str
    waybill_no: str | None


class VoidShop(BaseModel):
    shop_id: int
    shop_name: str
    waybills: list[VoidWaybill]


class PreviewBlocked(BaseModel):
    shop_id: int
    shop_name: str
    order_id: int
    order_no: str
    reason: str


class PreviewShopError(BaseModel):
    shop_id: int
    shop_name: str
    reason: str


class LabelPreviewResponse(BaseModel):
    preview_id: str
    mode: Literal["obtain", "fetch_and_ship"]
    shops: list[PreviewShop]
    blocked: list[PreviewBlocked]
    shop_errors: list[PreviewShopError]
    total_ready: int
    total_blocked: int
    dry_run: bool


class VoidPreviewResponse(BaseModel):
    preview_id: str
    mode: Literal["void"]
    shops: list[VoidShop]
    blocked: list[PreviewBlocked]
    shop_errors: list[PreviewShopError]
    total_ready: int
    total_blocked: int
    dry_run: bool


class ExecuteStarted(BaseModel):
    preview_id: str
    mode: str
    shop_ids: list[int]
