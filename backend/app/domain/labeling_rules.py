"""取号前置规则（纯函数）：账户与快递选择、订单可取号判断、解密范围。

依据：backend 5.9 / 5.11、flows 7.3（DEC-05 / DEC-06）。只读输入、无 IO。
"""

from collections.abc import Mapping, Sequence
from typing import Any

from app.domain.base_data_rules import MONTHLY_ACCOUNT_BALANCE, account_usable
from app.domain.order_status import LocalOrderStatus, PlatformOrderStatus

# 可进入取号批次的本地状态（data-model 6.1）
LABELABLE_STATUSES: frozenset[str] = frozenset({
    LocalOrderStatus.SYNCED.value, LocalOrderStatus.PENDING_LABEL.value,
})
# 可作废面单的本地状态（已发货不允许作废）
VOIDABLE_STATUSES: frozenset[str] = frozenset({
    LocalOrderStatus.LABEL_OBTAINED.value, LocalOrderStatus.PRINTED.value,
})
# 允许解密的本地状态：仅待发货链路；已发货 / 已完成 / 已取消 / 已关闭一律不解除（flows 7.3 约束 1）
DECRYPTABLE_STATUSES: frozenset[str] = frozenset({
    LocalOrderStatus.SYNCED.value, LocalOrderStatus.PENDING_LABEL.value,
    LocalOrderStatus.LABEL_OBTAINED.value, LocalOrderStatus.PRINTED.value,
    LocalOrderStatus.EXCEPTION.value,
})
ORDER_ITEM_KEYS = ("sku_order_id", "product_id", "sku_id")


def select_account(
    accounts: Sequence[Mapping[str, Any]], courier_code: str
) -> Mapping[str, Any] | None:
    """usable 账户里：isDefault 优先，否则 balance 最大；月结（-1）视为不限量、排最前。"""
    usable = [
        a for a in accounts
        if a["courier_code"] == courier_code and account_usable(a["balance"])
    ]
    if not usable:
        return None
    default = [a for a in usable if a["is_default"]]
    pool = default or usable
    return max(pool, key=lambda a: (
        1 if a["balance"] == MONTHLY_ACCOUNT_BALANCE else 0, int(a["balance"] or 0)
    ))


def courier_options(
    templates: Sequence[Mapping[str, Any]], accounts: Sequence[Mapping[str, Any]]
) -> list[str]:
    """同时具备面单模板与可用账户的快递编码，按字母序稳定输出。"""
    template_couriers = {t["courier_code"] for t in templates if t["courier_code"]}
    account_couriers = {a["courier_code"] for a in accounts if account_usable(a["balance"])}
    return sorted(template_couriers & account_couriers)


def pick_courier(
    templates: Sequence[Mapping[str, Any]], accounts: Sequence[Mapping[str, Any]],
    preferred: str | None,
) -> str | None:
    options = courier_options(templates, accounts)
    if not options:
        return None
    if preferred and preferred in options:
        return preferred
    return options[0]


def order_blockers(
    platform_status: int | None, combine_id: str | None,
    items: Sequence[Mapping[str, Any]], has_active_waybill: bool, local_status: str,
) -> list[str]:
    """逐项列出该单不能取号的原因；空列表即可取号。"""
    reasons: list[str] = []
    if local_status not in LABELABLE_STATUSES:
        reasons.append(f"本地状态为 {local_status}，不可取号")
    if platform_status != int(PlatformOrderStatus.STOCK_UP):
        reasons.append("平台订单不是待发货状态")
    if not combine_id:
        reasons.append("缺少合单 ID（combine_id）")
    if has_active_waybill:
        reasons.append("已有有效面单")
    if not items:
        reasons.append("缺少商品行")
    elif any(not i.get(k) for i in items for k in ORDER_ITEM_KEYS):
        reasons.append("商品行缺少取号字段（sku_order_id / product_id / sku_id）")
    return reasons


def decrypt_allowed(local_status: str, platform_status: int | None) -> bool:
    """只对「待发货 / 待打单」链路解密（flows 7.3 约束 1）。"""
    return (
        platform_status == int(PlatformOrderStatus.STOCK_UP)
        and local_status in DECRYPTABLE_STATUSES
    )
