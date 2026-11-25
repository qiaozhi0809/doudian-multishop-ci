"""对账判定规则（纯函数，docs/api/reconcile.md G.3 / G.4）。

口径（G.2）：平台 order_status 3（已发货）/ 5（已完成）视为已发货；4（已关闭）视为未发货，
即使它仍可能携带运单号。快照一侧「已发货」= 上次同步的状态为 3/5，或带有运单号。

每单最多产出一类异常，判定顺序：本地已发货平台未发货 > 平台已发货本地未发货 > 运单号不一致。
"""

from dataclasses import dataclass

from app.domain.order_status import PlatformOrderStatus

LOCAL_SHIPPED_PLATFORM_NOT = "local_shipped_platform_not"
PLATFORM_SHIPPED_LOCAL_NOT = "platform_shipped_local_not"
WAYBILL_MISMATCH = "waybill_mismatch"
FINDING_KINDS: tuple[str, ...] = (
    LOCAL_SHIPPED_PLATFORM_NOT, PLATFORM_SHIPPED_LOCAL_NOT, WAYBILL_MISMATCH,
)
FINDING_TITLES: dict[str, str] = {
    LOCAL_SHIPPED_PLATFORM_NOT: "本地已发货、平台未发货",
    PLATFORM_SHIPPED_LOCAL_NOT: "平台已发货、本地未记录",
    WAYBILL_MISMATCH: "运单号不一致",
}

_PLATFORM_SHIPPED_STATUSES = frozenset({
    int(PlatformOrderStatus.SHIPPED), int(PlatformOrderStatus.COMPLETED),
})


@dataclass(frozen=True)
class FactView:
    """一单在某次同步时点的发货事实。两边（快照 / 本次平台）用同一结构比较。"""

    platform_status: int | None
    tracking_no: str | None
    company_code: str | None


@dataclass(frozen=True)
class Finding:
    kind: str
    local_status: int | None
    platform_status: int | None
    local_tracking_no: str | None
    platform_tracking_no: str | None
    local_company_code: str | None
    platform_company_code: str | None
    detail: str


def platform_shipped(status: int | None) -> bool:
    return status in _PLATFORM_SHIPPED_STATUSES


def snapshot_shipped(status: int | None, tracking_no: str | None) -> bool:
    return platform_shipped(status) or bool(tracking_no)


def classify(old: FactView | None, new: FactView) -> Finding | None:
    """比较本次同步前的快照与平台当前事实；无异常返回 None。"""
    snap_ship = old is not None and snapshot_shipped(old.platform_status, old.tracking_no)
    plat_ship = platform_shipped(new.platform_status)
    old_status = old.platform_status if old else None
    old_tracking = old.tracking_no if old else None
    old_company = old.company_code if old else None
    if snap_ship and not plat_ship:
        return Finding(
            LOCAL_SHIPPED_PLATFORM_NOT, old_status, new.platform_status,
            old_tracking, new.tracking_no, old_company, new.company_code,
            "快照显示已发货（或已有运单），平台当前不是已发货：可能回传后被撤销或平台状态回滚",
        )
    if plat_ship and not snap_ship:
        return Finding(
            PLATFORM_SHIPPED_LOCAL_NOT, old_status, new.platform_status,
            old_tracking, new.tracking_no, old_company, new.company_code,
            "平台已发货，本次同步前的快照没有发货记录：可能在其他地方人工发货",
        )
    if plat_ship and snap_ship and (old_tracking or "") != (new.tracking_no or ""):
        return Finding(
            WAYBILL_MISMATCH, old_status, new.platform_status,
            old_tracking, new.tracking_no, old_company, new.company_code,
            "两边都已发货，但运单号不同：可能换单或被修改",
        )
    return None
