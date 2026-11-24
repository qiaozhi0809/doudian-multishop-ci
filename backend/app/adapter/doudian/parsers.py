"""抖店响应 → 领域 DTO。字段名按脱敏样本（tests/fixtures/doudian）确认的真实结构。"""

from typing import Any

from app.adapter.doudian.errors import ParseError
from app.domain.models import (
    AddressDTO,
    CourierDTO,
    EbillAccountDTO,
    OrderDTO,
    OrderItemDTO,
    TemplateDTO,
)
from app.shared.time_bj import parse_platform_time


def _data(resp: dict) -> Any:
    if not isinstance(resp, dict) or "data" not in resp:
        raise ParseError("响应缺少 data")
    return resp["data"]


def _data_list(resp: dict, *path: str) -> list[dict]:
    node = _data(resp)
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise ParseError(f"响应缺少 data.{'.'.join(path)}")
        node = node[key]
    if not isinstance(node, list):
        raise ParseError("期望数组")
    return node


def _required(d: dict, key: str, what: str) -> Any:
    if d.get(key) in (None, ""):
        raise ParseError(f"{what} 缺少 {key}")
    return d[key]


def _opt_str(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _opt_int(value: Any) -> int | None:
    return None if value in (None, "") else int(value)


def _time(value: Any) -> str | None:
    try:
        return parse_platform_time(value)
    except ValueError as e:
        raise ParseError(str(e)) from e


# ---- 订单 ----

def _sku_id(item: dict) -> str | None:
    text = _opt_str(item.get("sku_id_str"))
    if text and text != "0":
        return text
    raw = item.get("sku_id")
    return None if raw in (None, "", 0, "0") else str(raw)


def _sku_spec(item: dict) -> str | None:
    values = [str(s["value"]) for s in item.get("sku_spec") or [] if s.get("value")]
    return "/".join(values) or None


def _parse_item(item: dict) -> OrderItemDTO:
    if item.get("combo_num") is None:
        raise ParseError("商品行缺少 combo_num")
    return OrderItemDTO(
        sku_order_id=str(_required(item, "item_order_id", "商品行")),
        product_id=_opt_str(item.get("product_id")),
        product_name=_opt_str(item.get("product_name")),
        sku_spec=_sku_spec(item),
        quantity=int(item["combo_num"]),
        price_cents=_opt_int(item.get("pay_amount")),
        sku_id=_sku_id(item),
    )


def _region(addr: dict) -> str | None:
    parts = [(addr.get(k) or {}).get("name") for k in ("province", "city", "town", "street")]
    return "".join(p for p in parts if p) or None


def _parse_order(o: dict) -> OrderDTO:
    recv = o.get("receiver_info") or {}
    return OrderDTO(
        order_no=str(_required(o, "shop_order_id", "订单")),
        platform_order_id=_opt_str(o.get("order_id")),
        combine_id=_opt_str(o.get("combine_id")),
        platform_status=_opt_int(o.get("order_status")),
        amount_cents=_opt_int(o.get("pay_amount")),
        create_time=_time(o.get("create_time")),
        pay_time=_time(o.get("pay_time")),
        exp_ship_time=_time(o.get("exp_ship_time")),
        buyer_nick=_opt_str(o.get("user_nickname")),
        receiver_name=_opt_str(recv.get("post_receiver")),
        receiver_phone=_opt_str(recv.get("post_tel")),
        receiver_region=_region(recv.get("post_addr") or {}),
        items=tuple(_parse_item(i) for i in o.get("product_item") or []),
        raw=o,
    )


def parse_orders(resp: dict) -> list[OrderDTO]:
    return [_parse_order(o) for o in _data_list(resp)]


def parse_tabcnt(resp: dict) -> dict[str, int]:
    """只取顶层整数计数（stock_up / exp_ship / ship_delay / in_aftersale 等）。"""
    data = _data(resp)
    if not isinstance(data, dict):
        raise ParseError("tabcnt 的 data 不是对象")
    return {
        k: v for k, v in data.items() if isinstance(v, int) and not isinstance(v, bool)
    }


# ---- 基础数据 ----

def parse_addresses(resp: dict) -> list[AddressDTO]:
    out = []
    for a in _data_list(resp, "address_list"):
        out.append(AddressDTO(
            address_id=str(_required(a, "id", "发货地址")),
            name=_opt_str(a.get("user_name")),
            phone=_opt_str(a.get("mobile") or a.get("phone")),
            region="".join(
                str(a.get(k)) for k in ("province_name", "city_name", "town_name", "street_name")
                if a.get(k)
            ) or None,
            detail=_opt_str(a.get("detail")),
            province_id=_opt_int(a.get("province_id")),
            province_name=_opt_str(a.get("province_name")),
            city_id=_opt_int(a.get("city_id")),
            city_name=_opt_str(a.get("city_name")),
            town_id=_opt_int(a.get("town_id")),
            town_name=_opt_str(a.get("town_name")),
            street_id=_opt_int(a.get("street_id")),
            street_name=_opt_str(a.get("street_name")),
            is_default=a.get("is_send_default") == 1,
            raw=a,
        ))
    return out


def parse_ebill_accounts(resp: dict, courier_code: str) -> list[EbillAccountDTO]:
    out = []
    for a in _data_list(resp, "accounts"):
        net_code = a.get("netCode") or a.get("monthlyAccountOrNetCode")
        if not net_code:
            raise ParseError("面单账户缺少 netCode / monthlyAccountOrNetCode")
        out.append(EbillAccountDTO(
            courier_code=courier_code,
            ebill_id=str(_required(a, "eBillId", "面单账户")),
            net_code=str(net_code),
            net_name=_opt_str(a.get("netName")),
            account_type=_opt_int(a.get("accountType")),
            balance=_opt_int(a.get("balance")),
            is_default=bool(a.get("isDefault")),
            raw=a,
        ))
    return out


# 每组模板列表：(列表字段, 模板编码字段, 名称字段, 是否自定义)
_TEMPLATE_LISTS = (
    ("customTempList", "customTempCode", "customTempName", True),
    ("parentTempList", "parentTempCode", "parentTempName", False),
    ("publicTempList", "customTempCode", "customTempName", False),
)


def parse_templates(resp: dict) -> list[TemplateDTO]:
    """按快递分组展开。官方模板与公共模板可能同 code，按 code 去重（自定义优先）。"""
    seen: dict[str, TemplateDTO] = {}
    for group in _data_list(resp, "list"):
        courier = _opt_str(group.get("companyCode"))
        for list_key, code_key, name_key, is_custom in _TEMPLATE_LISTS:
            for t in group.get(list_key) or []:
                code = str(_required(t, code_key, "面单模板"))
                if code not in seen:
                    seen[code] = TemplateDTO(code, courier, _opt_str(t.get(name_key)), is_custom, t)
    return list(seen.values())


def parse_couriers(resp: dict) -> list[CourierDTO]:
    """eBills 与 favourites 合并去重；列表里出现即视为可用。"""
    data = _data(resp)
    if not isinstance(data, dict) or "eBills" not in data:
        raise ParseError("响应缺少 data.eBills")
    seen: dict[str, CourierDTO] = {}
    for c in [*data["eBills"], *(data.get("favourites") or [])]:
        code = str(_required(c, "company", "快递公司"))
        seen.setdefault(code, CourierDTO(code, _opt_str(c.get("name")), True, c))
    return list(seen.values())
