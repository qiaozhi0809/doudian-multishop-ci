"""飞鸽常驻页的重启节奏：按店记启动与刷新历史、连续失败次数，决定多久后再试。

退避时长与限额本身是 domain/im_rules 里的纯规则；这里只持有按店的状态，只在内存。
"""

from collections import Counter
from datetime import datetime, timedelta

from app.domain.im_rules import START_PER_DAY, StopReason, backoff_seconds, may_act

STABLE_RUN = timedelta(hours=1)  # 一次接收超过这么久，之前的连续失败不再累计
_DAY = timedelta(days=1)
_COUNTED: frozenset[StopReason] = frozenset({"error", "page_closed", "version_low"})


class ShopRetry:
    def __init__(self) -> None:
        self.reload_history: list[datetime] = []  # 交给 ImSession 原地追加，重启不清零
        self._starts: list[datetime] = []
        self._failures: Counter[bool] = Counter()  # 键：是否版本过低（单独计次）

    def wait_for_start(self, now: datetime) -> float | None:
        """现在能启动返回 None；超过每日上限返回还要等几秒。"""
        self._starts = [at for at in self._starts if now - at < _DAY]
        if may_act(self._starts, now, min_gap=timedelta(0), per_day=START_PER_DAY):
            return None
        return (self._starts[-START_PER_DAY] + _DAY - now).total_seconds()

    def record_start(self, now: datetime) -> None:
        self._starts.append(now)

    def delay_after(self, reason: StopReason, ran: timedelta) -> float | None:
        """这一轮以 reason 结束、接收了 ran 之后多久再试；None = 不自动重试。"""
        if ran >= STABLE_RUN:
            self._failures.clear()
        key = reason == "version_low"
        if reason in _COUNTED:
            self._failures[key] += 1
        return backoff_seconds(reason, self._failures[key])

    def reset(self) -> None:
        """清零连续失败次数（手动重新连接）；启动与刷新限额不清。"""
        self._failures.clear()
