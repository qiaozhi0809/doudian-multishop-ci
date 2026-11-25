"""取号 / 一体 / 作废请求体构造（字段依据 docs/api/write.md A.2.2 / A.2.5 / A.2.6 的实测样本）。

纯函数：输入是本地行（store 读出的映射），输出是抖店协议 JSON。
公共参数由 `FxgClient` 注入，不在这里拼。
"""

import json
from collections.abc import Mapping, Sequence
from typing import Any

# 协议常量（A.2 已验证值；集中在此，业务代码不散落字面量）
SEND_TYPE_E_WAYBILL = "3"  # 电子面单发货
FETCH_TYPE = 1
ORDER_TYPE = 0
OBTAIN_VERSION = 1
FETCH_AND_SHIP_VERSION = 0
IS_DAVINCI = True
IS_CANCEL_COMBINE = False
IS_SUB_BUNDLE_ITEM = True
_EXP_TYPE_PARAM = "expType"


def address_payload(addr: Mapping[str, Any]) -> dict[str, Any]:
    """发货地址（店铺自己的地址）。`address` 为「省市区街道 + 详细地址」的完整串。"""
    names = "".join(
        str(addr.get(k) or "") for k in
        ("province_name", "city_name", "town_name", "street_name")
    )
    region = names or str(addr.get("region") or "")
    address_id = addr["address_id"]
    return {
        "id": int(address_id) if str(address_id).isdigit() else address_id,
        "province_id": addr.get("province_id"),
        "province_name": addr.get("province_name"),
        "city_id": addr.get("city_id"),
        "city_name": addr.get("city_name"),
        "town_id": addr.get("town_id"),
        "town_name": addr.get("town_name"),
        "street_id": addr.get("street_id"),
        "street_name": addr.get("street_name"),
        "detail": addr.get("detail"),
        "address": region + str(addr.get("detail") or ""),
        "user_name": addr.get("name"),
        "mobile": addr.get("phone"),
    }


def order_list_payload(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """rows: 含 `order_no`、`combine_id` 与 `items`（商品行映射）的订单行。"""
    return [
        {
            "combine_id": row["combine_id"],
            "is_cancel_combine": IS_CANCEL_COMBINE,
            "shop_order_id": row["order_no"],
            "sku_orders": [
                {
                    "sku_order_id": item["sku_order_id"],
                    "sku_id": item["sku_id"],
                    "product_id": item["product_id"],
                    "product_cnt": item["quantity"],
                }
                for item in row["items"]
            ],
            "is_sub_bundle_item": IS_SUB_BUNDLE_ITEM,
        }
        for row in rows
    ]


def obtain_body(
    *, courier_code: str, template_code: str, address: Mapping[str, Any], exp_type: str,
    ebill_id: str, net_code: str, order_list: list[dict[str, Any]], printer: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "logistics_company_code": courier_code,
        "logistics_template_code": template_code,
        "address": address_payload(address) if "address_id" in address else dict(address),
        "transport": json.dumps({_EXP_TYPE_PARAM: exp_type}, ensure_ascii=False),
        "net_code": net_code,
        "ebill_id": ebill_id,
        "shop_order_list": order_list,
        "fetch_type": FETCH_TYPE,
        "is_davinci": IS_DAVINCI,
        "order_type": ORDER_TYPE,
        "version": OBTAIN_VERSION,
    }
    if printer:
        body["printer"] = printer
    return body


def fetch_and_ship_body(
    *, courier_code: str, template_code: str, address: Mapping[str, Any], exp_type: str,
    ebill_id: str, net_code: str, order_list: list[dict[str, Any]],
    added_services: Sequence[Any] = (), printer: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "send_type": SEND_TYPE_E_WAYBILL,
        "fetch_type": FETCH_TYPE,
        "logistics_company_code": courier_code,
        "logistics_template_code": template_code,
        "address": address_payload(address) if "address_id" in address else dict(address),
        "transport": json.dumps({_EXP_TYPE_PARAM: exp_type}, ensure_ascii=False),
        "net_code": net_code,
        "ebill_id": ebill_id,
        "added_services": list(added_services),
        "shop_order_list": order_list,
        "is_davinci": IS_DAVINCI,
        "version": FETCH_AND_SHIP_VERSION,
    }
    if printer:
        body["printer"] = printer
    return body


def cancel_body(waybills: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """waybills: 含 `waybill_no` 与 `courier_code` 的面单行。"""
    return {
        "cancel_list": [
            {"tracking_no": w["waybill_no"], "logistics_company_code": w["courier_code"]}
            for w in waybills
        ],
    }
