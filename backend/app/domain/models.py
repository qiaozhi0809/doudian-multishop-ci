"""领域传输对象：adapter 产出，store 消费。时间字段均为 ISO-8601 UTC 字符串，金额为整数分。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OrderItemDTO:
    sku_order_id: str
    product_id: str | None
    product_name: str | None
    sku_spec: str | None
    quantity: int
    price_cents: int | None  # 取商品行 pay_amount；数量大于 1 时是单价还是行合计待样本确认
    sku_id: str | None


@dataclass(frozen=True)
class OrderDTO:
    order_no: str
    platform_order_id: str | None
    combine_id: str | None
    platform_status: int | None
    amount_cents: int | None
    create_time: str | None
    pay_time: str | None
    exp_ship_time: str | None
    buyer_nick: str | None
    receiver_name: str | None
    receiver_phone: str | None
    receiver_region: str | None
    items: tuple[OrderItemDTO, ...]
    raw: dict


@dataclass(frozen=True)
class AddressDTO:
    address_id: str
    name: str | None
    phone: str | None
    region: str | None
    detail: str | None
    province_id: int | None
    province_name: str | None
    city_id: int | None
    city_name: str | None
    town_id: int | None
    town_name: str | None
    street_id: int | None
    street_name: str | None
    is_default: bool
    raw: dict


@dataclass(frozen=True)
class EbillAccountDTO:
    courier_code: str
    ebill_id: str
    net_code: str
    net_name: str | None
    account_type: int | None
    balance: int | None  # 面单张数；-1 表示月结账户（见 base_data_rules.MONTHLY_ACCOUNT_BALANCE）
    is_default: bool
    raw: dict


@dataclass(frozen=True)
class TemplateDTO:
    template_code: str
    courier_code: str | None
    name: str | None
    is_custom: bool
    raw: dict


@dataclass(frozen=True)
class CourierDTO:
    courier_code: str
    name: str | None
    enabled: bool
    raw: dict


# ---- M2 取号 / 作废 / 解密 ----


@dataclass(frozen=True)
class FetchSuccess:
    """一张新面单。`order_nos` 为平台响应里该面单覆盖的订单号（可能多单合包）。"""

    order_nos: tuple[str, ...]
    courier_code: str
    tracking_no: str
    template_code: str | None
    print_data: str | None
    sign: str | None


@dataclass(frozen=True)
class FetchFailure:
    """失败项。平台可能只给 `fail_msg` 而不带订单引用（A.2.2 第 8 条）。"""

    order_nos: tuple[str, ...]
    fail_msg: str


@dataclass(frozen=True)
class FetchResult:
    success: tuple[FetchSuccess, ...]
    failures: tuple[FetchFailure, ...]


@dataclass(frozen=True)
class CancelSuccess:
    courier_code: str
    tracking_no: str


@dataclass(frozen=True)
class CancelFailure:
    courier_code: str | None
    tracking_no: str | None
    fail_msg: str


@dataclass(frozen=True)
class CancelResult:
    success: tuple[CancelSuccess, ...]
    failures: tuple[CancelFailure, ...]
    fail_msg: str | None


@dataclass(frozen=True)
class ProductTypes:
    exp_type: str | None
    added_services: tuple[dict, ...]


@dataclass(frozen=True)
class ReceiverInfo:
    """收件人明文：只在内存中使用，不落库（flows 7.3）。"""

    name: str | None
    phone: str | None
    region: str | None
    detail: str | None
    expire_at: str | None
    verify_type: str | None


@dataclass(frozen=True)
class PrintInfo:
    """一张面单的打印数据（取号响应或 batchGetPrintInfos 补打，flows 10 节）。

    `params` 对应组件 documents.standard.params（取自 OAuth）；取号响应没有 OAuth。
    """

    tracking_no: str
    print_data: str | None
    sign: str | None
    template_url: str | None
    params: str | None
    custom_print_data: str | None
    custom_template_url: str | None
