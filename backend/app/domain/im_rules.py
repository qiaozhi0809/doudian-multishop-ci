"""飞鸽只读聚合的纯规则：状态、退避与限额、选店、待回复与买家等待（docs/api/flybird.md）。"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

ImState = Literal[
    "off", "queued", "starting", "running", "backoff", "needs_refresh", "stopped"
]
STATE_LABELS: dict[ImState, str] = {
    "off": "未开启",
    "queued": "排队中",
    "starting": "启动中",
    "running": "接收中",
    "backoff": "稍后重试",
    "needs_refresh": "需重新连接",
    "stopped": "已停止",
}
StopReason = Literal[
    "error", "version_low", "preempted", "ineligible", "page_closed", "lifetime", "shutdown"
]

START_PER_DAY = 24  # 含每日重启
RELOAD_MIN_GAP = timedelta(minutes=10)
RELOAD_PER_DAY = 6
DEBOUNCE_S = 30
POLL_S = 300
VERSION_LOW_MAX = 3
WAIT_ALERT = timedelta(minutes=3)
WAIT_TICK_S = 30
MESSAGE_RETENTION = timedelta(days=30)
# 算作「已回复」的发送方；只认人工回复时去掉 robot
REPLY_ROLES = frozenset({"agent", "robot"})

_BUYER_ROLE = "buyer"
_BACKOFF_BASE_S = 60
_BACKOFF_CAP_S = 3600
_PREEMPTED_BACKOFF_S = 60
_DAY = timedelta(days=1)
_ACTIVE = "active"
_BLOCKING_EGRESS = frozenset({"unreachable", "changed", "duplicate"})
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


class RoleMessage(Protocol):
    """规则只看发送方与时间；`adapter.flybird.parse.Message` 满足它（domain 不依赖 adapter）。"""

    @property
    def sender_role(self) -> str: ...

    @property
    def sent_at(self) -> str: ...


# ---- 退避与限额 ----


def backoff_seconds(reason: StopReason, attempt: int) -> float | None:
    """停止后多久重试；attempt 为连续第几次（从 1 起）。None = 不自动重试。"""
    if reason in ("ineligible", "shutdown"):
        return None
    if reason == "lifetime":
        return 0
    if reason == "preempted":
        return _PREEMPTED_BACKOFF_S
    if reason == "version_low" and attempt >= VERSION_LOW_MAX:
        return None
    return min(_BACKOFF_BASE_S * 2 ** max(attempt - 1, 0), _BACKOFF_CAP_S)


def may_act(
    history: Sequence[datetime], now: datetime, *, min_gap: timedelta, per_day: int
) -> bool:
    """按历史时刻判断现在能否再启动 / 刷新一次；「每天」指过去 24 小时。"""
    if any(now - at < min_gap for at in history):
        return False
    return sum(now - at < _DAY for at in history) < per_day


# ---- 选店 ----


def block_reason(shop: Mapping[str, Any], profile: Mapping[str, Any] | None) -> ImState | None:
    """不该开常驻页时返回应显示的状态。四个条件都在 shop 行上，profile 目前不参与判断。"""
    if not shop["im_enabled"]:
        return "off"
    if (
        shop["status"] != _ACTIVE
        or shop["paused_reason"]
        or shop["egress_status"] in _BLOCKING_EGRESS
    ):
        return "stopped"
    return None


# ---- 待回复与等待计时（消息按时间正序传入；平台消息不计） ----


def _unanswered(msgs: Sequence[RoleMessage]) -> list[RoleMessage]:
    """最后一条客服或智能客服消息之后的买家消息。"""
    pending: list[RoleMessage] = []
    for message in msgs:
        if message.sender_role in REPLY_ROLES:
            pending.clear()
        elif message.sender_role == _BUYER_ROLE:
            pending.append(message)
    return pending


def pending_counts(msgs_by_conv: Mapping[str, Sequence[RoleMessage]]) -> dict[str, int]:
    """每个会话的待回复买家消息数（平台的 unreadCount 不可用，flybird.md §2）。"""
    return {conv: len(_unanswered(msgs)) for conv, msgs in msgs_by_conv.items()}


def waiting_since(msgs: Sequence[RoleMessage]) -> str | None:
    """买家从何时起在等回复；没有待回复消息返回 None。"""
    pending = _unanswered(msgs)
    return pending[0].sent_at if pending else None


def overdue_count(waits: Mapping[str, str | None], now: datetime) -> int:
    """等待超过 WAIT_ALERT 的会话数；now 须带时区。"""
    return sum(
        since is not None
        and now - datetime.strptime(since, _ISO_FMT).replace(tzinfo=UTC) > WAIT_ALERT
        for since in waits.values()
    )
