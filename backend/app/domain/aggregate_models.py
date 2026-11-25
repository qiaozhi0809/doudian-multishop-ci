"""M5 只读聚合的领域传输对象：adapter 产出，store 消费。

字段依据 docs/api/aftersale.md（附录 E）、catalog.md（附录 D）、fund.md（附录 F）。
金额一律整数分；时间一律 ISO-8601 UTC 字符串；`raw` 保留平台原始报文。
"""

from dataclasses import dataclass

# ---- 售后（附录 E.1）----


@dataclass(frozen=True)
class AftersaleDTO:
    after_sale_id: str
    order_no: str | None  # after_sale_info.related_id（关联订单号）
    type: int | None  # after_sale_type 数字枚举（平台未公开取值）
    status: int | None  # after_sale_status 数字枚举（平台未公开取值）
    refund_amount_cents: int | None
    status_deadline: str | None  # 平台 unix 秒；0 表示已完结 → None
    apply_time: str | None
    raw: dict


# ---- 商品 / 库存（附录 D.1 / D.2）----


@dataclass(frozen=True)
class ProductDTO:
    product_id: str
    name: str | None
    status: str | None
    tab: str | None
    price_lower_cents: int | None
    price_higher_cents: int | None
    stock_num: int | None
    sell_num: int | None
    raw: dict


@dataclass(frozen=True)
class StockDTO:
    product_id: str
    total_stock_num: int | None
    spot_stock_num: int | None  # 现货
    future_stock_num: int | None  # 未来库存；与现货分开展示，不可相加（附录 D.4）
    total_occupied_stock_num: int | None
    total_unoccupied_stock_num: int | None
    is_alarming: bool
    raw: dict


@dataclass(frozen=True)
class StockSummary:
    """库存列表响应顶层的店铺级统计（附录 D.2）。"""

    total: int
    stock_alarm_cnt: int
    sold_out_cnt: int
    stock_subscribe_cnt: int
    activity_stock_occupy_cnt: int
    channel_stock_occupy_cnt: int
    advised_increase_spot_cnt: int


@dataclass(frozen=True)
class WarehouseDTO:
    warehouse_id: str
    name: str | None
    raw: dict


@dataclass(frozen=True)
class GroupDTO:
    group_id: str
    name: str | None
    raw: dict


# ---- 资金（附录 F.1b / F.1c）----


@dataclass(frozen=True)
class FundUnsettledDTO:
    shop_order_no: str
    sku_order_no: str
    product_id: str | None
    income_amount_cents: int | None
    unsettled_amount_cents: int | None
    platform_service_fee_cents: int | None
    ecom_order_status: str | None
    expected_settle_time: str | None
    settle_period_detail: str | None
    raw: dict


@dataclass(frozen=True)
class MarginDTO:
    payable_cents: int | None
    balance_cents: int | None
    basic_payable_cents: int | None
    basic_balance_cents: int | None
    withdrawable_cents: int | None
    level: str | None
    raw: dict


# 账单金额是否已校准（附录 F.4）：平台字段名未确认时不得用猜测值冒充事实
BILL_AMOUNT_CONFIRMED = "confirmed"
BILL_AMOUNT_PENDING = "pending"


@dataclass(frozen=True)
class BillItemDTO:
    amount_cents: int  # 未校准时为 0，界面标注「待探明」
    amount_status: str  # BILL_AMOUNT_CONFIRMED | BILL_AMOUNT_PENDING
    amount_field: str | None  # 命中的平台字段名；未命中为 None
    raw: dict
