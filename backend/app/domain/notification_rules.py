"""通知规则：种类 → 档位、跳转链接、标题（纯函数，无 IO）。"""

from datetime import timedelta
from typing import Literal

Kind = Literal[
    "new_order", "new_aftersale", "login_expired", "egress_unreachable", "egress_changed",
    "egress_duplicate", "risk_paused", "ship_deadline", "batch_done", "batch_failed",
    "sync_failed", "sync_done", "reconcile_done", "recovered",
]
Level = Literal["strong", "medium", "weak"]
KindFamily = Literal["login", "egress", "risk", "deadline"]

LEVEL_BY_KIND: dict[Kind, Level] = {
    "new_aftersale": "strong",
    "login_expired": "strong",
    "egress_unreachable": "strong",
    "egress_changed": "strong",
    "egress_duplicate": "strong",
    "risk_paused": "strong",
    "ship_deadline": "strong",
    "new_order": "medium",
    "batch_failed": "medium",
    "sync_failed": "medium",
    "batch_done": "weak",
    "sync_done": "weak",
    "reconcile_done": "weak",
    "recovered": "weak",
}

# 恢复后这段时间内再犯 = 重开原记录并静默。
REOPEN_SILENT_WITHIN = timedelta(minutes=30)

_SHOP_PARAM = "shops"  # 与前端 shop-filter.ts 的 SHOP_FILTER_PARAM 一致
_SYNC_PAGES = {
    "orders": "/orders",
    "aftersales": "/aftersale",
    "products": "/catalog",
    "stock": "/stock",
    "fund": "/fund",
}
_SYNC_LABELS = {"orders": "订单", "aftersales": "售后", "products": "商品",
                "stock": "库存", "fund": "资金"}
_SHOP_STATE_TITLES = {
    "login_expired": "登录失效",
    "egress_unreachable": "出口不通",
    "egress_changed": "出口 IP 已变化",
    "egress_duplicate": "出口 IP 与其他店重复",
    "risk_paused": "风控暂停",
}

# 批量操作 → 标题前缀；detail 写成 batch_detail(...)，旧格式「失败数」按打单
_BATCH_LABELS = {"obtain": "打单", "fetch_and_ship": "打单发货", "void": "作废面单",
                 "ship": "发货", "print": "打印"}
# 需人工跟进的几类（为 0 的不写进标题）：失败、打单待核实、打印转手动补打
_FOLLOW_UP_LABELS = ("失败", "待核实", "需补打")


def batch_detail(op: str, failed: int = 0, verifying: int = 0, manual: int = 0) -> str:
    return f"{op}:{failed},{verifying},{manual}"


def _batch_title(count: int, detail: str | None) -> str:
    op, _, nums = (detail or "").rpartition(":")
    counts = [int(n) for n in nums.split(",") if n.strip().isdigit()] if nums else []
    parts = [f"成功 {count}"] + [
        f"{label} {n}" for label, n in zip(_FOLLOW_UP_LABELS, counts, strict=False) if n > 0]
    return f"{_BATCH_LABELS.get(op, '打单')}完成：" + "，".join(parts)


def state_key(kind_family: KindFamily, shop_id: int) -> str:
    return f"{kind_family}:{shop_id}"


def _with_query(path: str, params: list[tuple[str, str]]) -> str:
    return path + ("?" + "&".join(f"{k}={v}" for k, v in params) if params else "")


def link_for(
    kind: Kind, shop_id: int | None, *, sync_type: str | None = None, overdue: bool = False,
) -> str:
    """overdue：临近超时的店里已有超时订单 → 跳「已超时」筛选（exp_ship 不含已超时）。"""
    shop = [(_SHOP_PARAM, str(shop_id))] if shop_id is not None else []
    if kind == "new_order":
        return _with_query("/orders", shop)
    if kind == "new_aftersale":
        return _with_query("/aftersale", [("view", "todo"), *shop])
    if kind == "ship_deadline":
        quick = "ship_delay" if overdue else "exp_ship"
        return _with_query("/orders", [("quick", quick), *shop])
    if kind in _SHOP_STATE_TITLES:
        # 店铺页高亮参数名为 shop（Task 7 前端实现）
        return _with_query("/shops", [("shop", str(shop_id))] if shop_id is not None else [])
    if kind in ("batch_done", "batch_failed"):
        return "/labeling"
    if kind in ("sync_done", "sync_failed"):
        return _with_query(_SYNC_PAGES.get(sync_type or "", "/dashboard"), shop)
    if kind == "reconcile_done":
        return "/reconcile"
    return "/dashboard"  # recovered 等：由调用方沿用原记录链接


def title_for(kind: Kind, *, shop_name: str | None, count: int, detail: str | None) -> str:
    name = shop_name or ""
    prefix = f"{name} " if name else ""
    if kind == "new_order":
        return f"{prefix}新增 {count} 单待发货"
    if kind == "new_aftersale":
        return f"{prefix}新增 {count} 个售后"
    if kind == "ship_deadline":
        return f"{prefix}{count} 单临近发货超时"
    if kind in _SHOP_STATE_TITLES:
        return f"{prefix}{_SHOP_STATE_TITLES[kind]}"
    if kind == "recovered":
        return f"{prefix}已恢复：{detail}" if detail else f"{prefix}已恢复"
    if kind in ("batch_done", "batch_failed"):
        return _batch_title(count, detail)
    if kind in ("sync_done", "sync_failed"):
        label = _SYNC_LABELS.get(detail or "", detail or "")
        return f"{prefix}{label}同步{'完成' if kind == 'sync_done' else '失败'}"
    return "对账完成"
