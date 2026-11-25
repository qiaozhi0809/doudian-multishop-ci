"""发货接口的请求 / 响应模型。"""

from pydantic import BaseModel, Field

MAX_SHIP_BATCH = 200


class ShipPoolRow(BaseModel):
    id: int
    shop_id: int
    shop_name: str
    order_no: str
    status: str
    platform_status: int | None
    amount_cents: int | None
    pay_time: str | None
    exp_ship_time: str | None
    waybill_id: int
    courier_code: str
    tracking_no: str
    printed: bool


class ShipPoolPage(BaseModel):
    items: list[ShipPoolRow]
    total: int
    page: int
    page_size: int


class ShipCheckRequest(BaseModel):
    order_ids: list[int] = Field(min_length=1, max_length=MAX_SHIP_BATCH)


class ShopCheckOut(BaseModel):
    shop_id: int
    shop_name: str
    order_nos: list[str]
    total: int
    double_check_num: int
    double_check_detail: list[dict]
    without_aftersale: list[str]
    place_holder: dict | None


class BlockedShipOut(BaseModel):
    order_id: int
    order_no: str
    shop_name: str
    reason: str


class ShopCheckErrorOut(BaseModel):
    shop_id: int
    shop_name: str
    reason: str


class ShipCheckResponse(BaseModel):
    shops: list[ShopCheckOut]
    blocked: list[BlockedShipOut]
    shop_errors: list[ShopCheckErrorOut]
    total_orders: int
    double_check_total: int
    dry_run: bool


class ShipRequest(BaseModel):
    order_ids: list[int] = Field(min_length=1, max_length=MAX_SHIP_BATCH)
    double_check_ack: bool = False


class ShipStartedOut(BaseModel):
    batch_id: str
    shop_ids: list[int]
    package_count: int
    order_count: int


class ShipmentRow(BaseModel):
    id: int
    batch_id: str
    shop_id: int
    order_id: int
    waybill_id: int | None
    courier_code: str
    tracking_no: str
    status: str
    fail_msg: str | None
    created_at: str
    finished_at: str | None


class ShipBatchResponse(BaseModel):
    batch_id: str
    ok: int
    failed: int
    pending: int
    items: list[ShipmentRow]
