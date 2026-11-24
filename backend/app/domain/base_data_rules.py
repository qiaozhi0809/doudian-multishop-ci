"""基础数据规则：取号就绪判定（纯函数）。"""

# 月结账户（如京东）不按张数计费，平台返回 balance = -1
MONTHLY_ACCOUNT_BALANCE = -1


def account_usable(balance: int | None) -> bool:
    return balance is not None and (balance > 0 or balance == MONTHLY_ACCOUNT_BALANCE)


def compute_readiness(
    has_default_address: bool, template_couriers: set[str], usable_account_couriers: set[str]
) -> tuple[bool, list[str]]:
    """就绪：有默认发货地址，且至少一家快递同时有面单模板和可用面单账户。"""
    reasons: list[str] = []
    if not has_default_address:
        reasons.append("没有默认发货地址")
    if not template_couriers & usable_account_couriers:
        if not template_couriers:
            reasons.append("没有面单模板")
        if not usable_account_couriers:
            reasons.append("没有可用面单账户（无账户或余额为 0）")
        if template_couriers and usable_account_couriers:
            reasons.append("没有快递同时具备面单模板和可用面单账户")
    return not reasons, reasons
