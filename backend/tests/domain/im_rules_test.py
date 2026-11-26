from datetime import UTC, datetime, timedelta
from typing import get_args

import pytest

from app.adapter.flybird.parse import Message, SenderRole
from app.domain.im_rules import (
    DEBOUNCE_S,
    MESSAGE_RETENTION,
    POLL_S,
    RELOAD_MIN_GAP,
    RELOAD_PER_DAY,
    REPLY_ROLES,
    START_PER_DAY,
    STATE_LABELS,
    VERSION_LOW_MAX,
    WAIT_ALERT,
    WAIT_TICK_S,
    ImState,
    backoff_seconds,
    block_reason,
    may_act,
    overdue_count,
    pending_counts,
    waiting_since,
)

NOW = datetime(2026, 12, 1, 10, 0, 0, tzinfo=UTC)


def msgs(*items: tuple[SenderRole, str]) -> list[Message]:
    """(发送方, "时:分") 序列 → 同一虚构会话里按顺序排列的消息。"""
    return [
        Message("conv-test-1", f"msg-test-{i}", role, "在吗", f"2026-12-01T{clock}:00Z")
        for i, (role, clock) in enumerate(items, start=1)
    ]


# ---- 常量 ----


def test_every_state_has_label():
    assert set(STATE_LABELS) == set(get_args(ImState))
    assert [STATE_LABELS[s] for s in get_args(ImState)] == [
        "未开启", "排队中", "启动中", "接收中", "稍后重试", "需重新连接", "已停止",
    ]


def test_limits_match_plan():
    assert (START_PER_DAY, RELOAD_PER_DAY, VERSION_LOW_MAX) == (24, 6, 3)
    assert (DEBOUNCE_S, POLL_S, WAIT_TICK_S) == (30, 300, 30)
    assert RELOAD_MIN_GAP == timedelta(minutes=10)
    assert WAIT_ALERT == timedelta(minutes=3)
    assert MESSAGE_RETENTION == timedelta(days=30)
    assert REPLY_ROLES == frozenset({"agent", "robot"})


# ---- 待回复 ----


def test_pending_counts_after_last_reply():
    conv = msgs(("buyer", "10:00"), ("agent", "10:01"), ("buyer", "10:02"), ("buyer", "10:03"))

    assert pending_counts({"conv-test-1": conv}) == {"conv-test-1": 2}


def test_pending_counts_robot_reply_clears():
    conv = msgs(("buyer", "10:00"), ("buyer", "10:01"), ("robot", "10:02"))

    assert pending_counts({"conv-test-1": conv}) == {"conv-test-1": 0}


def test_pending_counts_platform_only_and_between_buyers():
    result = pending_counts({
        "conv-test-1": msgs(("platform", "10:00")),
        "conv-test-2": msgs(("buyer", "10:00"), ("platform", "10:01"), ("buyer", "10:02")),
        "conv-test-3": [],
    })

    assert result == {"conv-test-1": 0, "conv-test-2": 2, "conv-test-3": 0}


# ---- 退避与限额 ----


@pytest.mark.parametrize("reason", ["error", "page_closed"])
def test_backoff_error_doubles_and_caps(reason):
    delays = [backoff_seconds(reason, attempt) for attempt in range(1, 9)]

    assert delays == [60, 120, 240, 480, 960, 1920, 3600, 3600]
    assert backoff_seconds(reason, 10_000) == 3600


def test_backoff_attempt_below_one_counts_as_first():
    assert backoff_seconds("error", 0) == 60


def test_backoff_version_low_stops_after_max():
    assert backoff_seconds("version_low", 1) == 60
    assert backoff_seconds("version_low", VERSION_LOW_MAX - 1) == 120
    assert backoff_seconds("version_low", VERSION_LOW_MAX) is None
    assert backoff_seconds("version_low", VERSION_LOW_MAX + 1) is None


@pytest.mark.parametrize("attempt", [1, 5])
def test_backoff_preempted_fixed_60(attempt):
    assert backoff_seconds("preempted", attempt) == 60


def test_backoff_lifetime_zero():
    assert backoff_seconds("lifetime", 1) == 0


@pytest.mark.parametrize("reason", ["ineligible", "shutdown"])
def test_backoff_ineligible_none(reason):
    assert backoff_seconds(reason, 1) is None


def test_may_act_gap_and_daily_cap():
    gap = timedelta(minutes=10)

    def allowed(*ages: timedelta, per_day: int = 3) -> bool:
        return may_act([NOW - age for age in ages], NOW, min_gap=gap, per_day=per_day)

    assert allowed()
    assert not allowed(gap - timedelta(seconds=1))
    assert allowed(gap)
    # 顺序无关：最近一次不在列表末尾也要看到
    assert not allowed(timedelta(minutes=1), timedelta(hours=2))
    assert allowed(timedelta(hours=1), timedelta(hours=2))
    assert not allowed(timedelta(hours=1), timedelta(hours=2), timedelta(hours=3))
    # 满 24 小时的记录不再占当日名额
    assert allowed(timedelta(hours=1), timedelta(hours=2), timedelta(hours=24))
    assert not allowed(
        timedelta(hours=1), timedelta(hours=2), timedelta(hours=24) - timedelta(seconds=1))


def test_may_act_zero_gap_only_applies_daily_cap():
    assert may_act([NOW], NOW, min_gap=timedelta(0), per_day=2)
    assert not may_act([NOW, NOW], NOW, min_gap=timedelta(0), per_day=2)


# ---- 选店 ----


def shop(**changes: object) -> dict[str, object]:
    row = {"im_enabled": 1, "status": "active", "paused_reason": None, "egress_status": "ok"}
    return {**row, **changes}


@pytest.mark.parametrize(("changes", "expected"), [
    ({}, None),
    ({"egress_status": "unchecked"}, None),  # 启动时由 ShopRunner 检查出口
    ({"im_enabled": 0}, "off"),
    ({"im_enabled": 0, "status": "disabled"}, "off"),
    ({"status": "needs_login"}, "stopped"),
    ({"status": "disabled"}, "stopped"),
    ({"paused_reason": "risk_blocked:test"}, "stopped"),
    ({"egress_status": "unreachable"}, "stopped"),
    ({"egress_status": "changed"}, "stopped"),
    ({"egress_status": "duplicate"}, "stopped"),
])
def test_block_reason_cases(changes, expected):
    assert block_reason(shop(**changes), None) == expected


# ---- 等待计时 ----


def test_waiting_since_buyer_after_agent():
    conv = msgs(("agent", "10:00"), ("buyer", "10:01"), ("buyer", "10:02"))

    assert waiting_since(conv) == "2026-12-01T10:01:00Z"


def test_waiting_since_agent_last_is_none():
    assert waiting_since(msgs(("buyer", "10:00"), ("agent", "10:01"))) is None


def test_waiting_since_robot_reply_counts():
    assert waiting_since(msgs(("buyer", "10:00"), ("robot", "10:01"))) is None


def test_waiting_since_ignores_platform():
    conv = msgs(("agent", "10:00"), ("buyer", "10:01"), ("platform", "10:02"))

    assert waiting_since(conv) == "2026-12-01T10:01:00Z"
    assert waiting_since(msgs(("agent", "10:00"), ("platform", "10:01"))) is None


def test_waiting_since_no_messages_is_none():
    assert waiting_since([]) is None


def test_overdue_count_strictly_over_3_minutes():
    waits = {
        "conv-test-1": "2026-12-01T09:57:00Z",  # 恰好 3 分钟
        "conv-test-2": "2026-12-01T09:56:59Z",  # 3 分 1 秒
        "conv-test-3": None,
    }

    assert overdue_count(waits, NOW) == 1
