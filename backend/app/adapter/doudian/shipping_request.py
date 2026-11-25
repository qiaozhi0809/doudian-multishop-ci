"""发货前检查与发货的请求体构造（字段依据 docs/api/write.md A.2.3 / A.2.4 的实测样本）。

纯函数：公共参数由 `FxgClient` 注入，不在这里拼。
"""

from collections.abc import Mapping, Sequence
from typing import Any

from app.adapter.doudian.label_request import SEND_TYPE_E_WAYBILL, address_payload

SEND_CHECK_TYPE = 13  # 发货前检查（write.md A.2.3 已验证值）


def sendcheck_body(
    order_nos: Sequence[str], address: Mapping[str, Any]
) -> dict[str, Any]:
    """orderIds 是平台店铺订单号（shop_order_id），不是本地主键。"""
    return {
        "orderIds": [str(no) for no in order_nos],
        "checkType": SEND_CHECK_TYPE,
        "address": address_payload(address) if "address_id" in address else dict(address),
    }


def deliver_body(packages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """packages: 含 `courier_code` 与 `tracking_no` 的包裹行；按运单号发货（A.2.4）。"""
    return {
        "send_type": SEND_TYPE_E_WAYBILL,
        "batch_deliver_packages": [
            {
                "logistics_company_code": p["courier_code"],
                "tracking_no": p["tracking_no"],
            }
            for p in packages
        ],
    }
