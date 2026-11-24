"""订单接口的响应模型。"""

from typing import Literal

from pydantic import BaseModel

LocalStatus = Literal[
    "synced", "pending_label", "label_obtained", "printed",
    "shipped", "exception", "cancelled", "closed",
]


class OrderItem(BaseModel):
    sku_order_id: str | None
    product_id: str | None
    product_name: str | None
    sku_spec: str | None
    quantity: int
    price_cents: int | None


class OrderRow(BaseModel):
    id: int
    shop_id: int
    shop_name: str
    order_no: str
    platform_status: int | None
    status: LocalStatus
    exception_reason: str | None
    amount_cents: int | None
    pay_time: str | None
    exp_ship_time: str | None
    items: list[OrderItem]


class OrderPage(BaseModel):
    items: list[OrderRow]
    total: int
    page: int
    page_size: int


class OrderCounts(BaseModel):
    stock_up: int
    exp_ship: int
    ship_delay: int
    in_aftersale: int


class ShopOrderCounts(BaseModel):
    shop_id: int
    counts: OrderCounts | None = None
    source: Literal["upstream", "error"]
    error: str | None = None


class OrderCountsResponse(BaseModel):
    shops: list[ShopOrderCounts]


class SyncStarted(BaseModel):
    started: list[int]
    already_running: list[int]
