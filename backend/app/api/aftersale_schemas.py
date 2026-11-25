"""售后接口的响应模型（只读聚合）。"""

from pydantic import BaseModel, Field


class AftersaleButton(BaseModel):
    code: str
    text: str | None = None
    disabled: bool = False


class AftersaleDisplay(BaseModel):
    status_text: str | None = None
    type_text: str | None = None
    reason_text: str | None = None
    buyer_nick: str | None = None
    left_node_time: int | None = None
    platform_intervene: bool = False
    detail_link: str | None = None
    buttons: list[AftersaleButton] = Field(default_factory=list)
    order_info: dict = Field(default_factory=dict)


class AftersaleRow(BaseModel):
    id: int
    shop_id: int
    shop_name: str
    after_sale_id: str
    order_no: str | None
    type: int | None
    status: int | None
    refund_amount_cents: int | None
    status_deadline: str | None
    apply_time: str | None
    synced_at: str
    display: AftersaleDisplay


class AftersalePage(BaseModel):
    items: list[AftersaleRow]
    total: int
    page: int
    page_size: int


class ShopAftersaleCounts(BaseModel):
    shop_id: int
    source: str  # upstream | error
    counts: dict[str, int] | None = None
    pending_total: int = 0
    error: str | None = None
    fetched_at: str | None = None


class AftersaleCountsResponse(BaseModel):
    shops: list[ShopAftersaleCounts]


class ShopAftersaleSync(BaseModel):
    shop_id: int
    fetched: int
    complete: bool
    error: str | None = None
    synced_at: str | None = None


class AftersaleSyncResponse(BaseModel):
    shops: list[ShopAftersaleSync]


class AftersaleStatusOption(BaseModel):
    status: int
    label: str


class AftersaleStatusesResponse(BaseModel):
    items: list[AftersaleStatusOption]


class AftersaleDetail(BaseModel):
    shop_id: int
    after_sale_id: str
    detail: dict
