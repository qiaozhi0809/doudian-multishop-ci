"""资金接口的响应模型（只读聚合）。"""

from typing import Literal

from pydantic import BaseModel


class ShopFundSummary(BaseModel):
    shop_id: int
    shop_name: str
    unsettled_amount_cents: int
    unsettled_count: int
    margin_payable_cents: int | None = None
    margin_balance_cents: int | None = None
    margin_level: str | None = None
    margin_synced_at: str | None = None
    synced_at: str | None = None


class FundSummary(BaseModel):
    shops: list[ShopFundSummary]
    total_unsettled_amount_cents: int
    total_unsettled_count: int


class UnsettledDisplay(BaseModel):
    product_name: str | None = None
    sku_detail_text: str | None = None
    collection_subject_name: str | None = None
    settlement_delay_days: int | None = None


class UnsettledRow(BaseModel):
    id: int
    shop_id: int
    shop_name: str
    shop_order_no: str
    sku_order_no: str
    product_id: str | None
    income_amount_cents: int | None
    unsettled_amount_cents: int | None
    platform_service_fee_cents: int | None
    ecom_order_status: str | None
    expected_settle_time: str | None
    settle_period_detail: str | None
    synced_at: str
    display: UnsettledDisplay


class UnsettledPage(BaseModel):
    items: list[UnsettledRow]
    total: int
    page: int
    page_size: int


class MarginRow(BaseModel):
    id: int
    shop_id: int
    shop_name: str
    payable_cents: int | None
    balance_cents: int | None
    basic_payable_cents: int | None
    basic_balance_cents: int | None
    withdrawable_cents: int | None
    level: str | None
    synced_at: str


class MarginResponse(BaseModel):
    items: list[MarginRow]


# 账单金额字段待校准（附录 F.4）：pending = 未命中候选字段，界面显示 0 并标注「待探明」
BillAmountStatus = Literal["confirmed", "pending"]


class BillItem(BaseModel):
    amount_cents: int
    amount_status: BillAmountStatus
    amount_field: str | None = None
    raw: dict


class ShopBills(BaseModel):
    shop_id: int
    source: str
    total: int = 0
    items: list[BillItem] | None = None
    error: str | None = None
    fetched_at: str | None = None


class BillsResponse(BaseModel):
    days: int
    shops: list[ShopBills]


class ShopFundSync(BaseModel):
    shop_id: int
    unsettled_count: int
    margin_synced: bool
    note: str | None = None
    error: str | None = None
    synced_at: str | None = None


class FundSyncResponse(BaseModel):
    shops: list[ShopFundSync]
