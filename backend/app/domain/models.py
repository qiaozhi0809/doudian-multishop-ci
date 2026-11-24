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
    balance: int | None  # 面单张数；-1 表示月结账户，不计张数
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
