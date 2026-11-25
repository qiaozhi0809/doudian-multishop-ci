"""发货前置规则（纯函数，backend 5.6 / data-model 6.1）。

只判断「本地这一单能不能进入发货批次」；平台侧的发货前检查由 sendcheck 承担。
"""

from app.domain.order_status import LocalOrderStatus

# 只有已取号（未发货）的订单可以发货；label_obtained 也允许（电子面单不强制先打印）
SHIPPABLE_STATUSES: frozenset[str] = frozenset({
    LocalOrderStatus.LABEL_OBTAINED.value, LocalOrderStatus.PRINTED.value,
})
# 面单可用于发货的状态
SHIPPABLE_WAYBILL_STATUSES: frozenset[str] = frozenset({"active", "printed"})


def ship_blockers(
    local_status: str, waybill_status: str | None, waybill_no: str | None,
) -> list[str]:
    """逐项列出该单不能发货的原因；空列表即可发货。"""
    reasons: list[str] = []
    if local_status == LocalOrderStatus.SHIPPED.value:
        reasons.append("本地已是已发货")
    elif local_status not in SHIPPABLE_STATUSES:
        reasons.append(f"本地状态为 {local_status}，不可发货")
    if waybill_status is None:
        reasons.append("没有有效面单")
    elif waybill_status not in SHIPPABLE_WAYBILL_STATUSES:
        reasons.append(f"面单状态为 {waybill_status}，不可发货")
    if waybill_status is not None and not waybill_no:
        reasons.append("面单缺少运单号")
    return reasons
