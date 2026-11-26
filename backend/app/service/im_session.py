"""飞鸽单店只读循环：收消息、去重、存库、算待回复与买家等待、发事件、按限额刷新页面。

页面的生命周期（打开、关闭、重试）归调用方。消息正文只进内存与 save_messages，
不进日志与事件（事件只带数量）。
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import structlog

from app.adapter.flybird.endpoints import ERR_VERSION_TOO_LOW
from app.adapter.flybird.page import ImPage
from app.adapter.flybird.parse import ConvListResult, Message, SenderRole
from app.domain.im_rules import (
    DEBOUNCE_S,
    POLL_S,
    RELOAD_MIN_GAP,
    RELOAD_PER_DAY,
    WAIT_TICK_S,
    StopReason,
    may_act,
    overdue_count,
    pending_counts,
    waiting_since,
)
from app.service.events import IM_UNREAD_CHANGED, IM_WAIT_CHANGED, EventBus

log = structlog.get_logger()

CONV_TAIL = 50  # 每个会话在内存里保留的消息条数
_BUYER: SenderRole = "buyer"


@dataclass(frozen=True)
class ConvView:
    conversation_id: str
    key: str | None  # 页面会话列表里的会话键；列表里还没出现时为 None
    last_text: str = field(repr=False)  # 正文不进日志
    last_role: SenderRole
    last_at: str
    pending: int
    waiting_since: str | None


class ImSession:
    """on_frame / on_list / on_messages 交给 ImPage 作回调，须在事件循环线程里调用。"""

    def __init__(
        self, shop_id: int, page: ImPage, events: EventBus, *,
        clock: Callable[[], datetime],
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        reload_history: list[datetime],
        save_messages: Callable[[list[Message]], Awaitable[None]],
        history: list[Message],
    ) -> None:
        self._shop_id = shop_id
        self._page = page
        self._events = events
        self._clock = clock
        self._sleep = sleep
        self._reload_history = reload_history  # 调用方按店持有，会话重启不清零
        self._save = save_messages
        self._convs: dict[str, list[Message]] = {}
        self._keys: dict[str, str] = {}
        self._seen: set[str] = set()
        self._unsaved: list[Message] = []
        self._new = 0  # 还没发出去的新买家消息数
        self._dirty = False  # 有新消息还没发布
        self._quiet_until: datetime | None = None  # 去抖：此刻之前新消息只攒着
        self._sent_unread: int | None = None
        self._sent_wait: tuple[int, int] | None = None
        self._last_frame_at = clock()
        self._version_low = False
        self._stopped = False
        self._wake = asyncio.Event()
        self._absorb(history)  # 基线：不算新消息，不再存

    # ---- 页面回调 ----

    def on_frame(self, raw: bytes) -> None:
        self._last_frame_at = self._clock()

    def on_list(self, result: ConvListResult) -> None:
        self._keys.update(result.keys)
        if result.code == ERR_VERSION_TOO_LOW:
            self._version_low = True
            self._wake.set()

    def on_messages(self, msgs: list[Message]) -> None:
        fresh = self._absorb(msgs)
        if not fresh:
            return
        self._unsaved.extend(fresh)
        self._new += sum(m.sender_role == _BUYER for m in fresh)
        self._dirty = True
        self._wake.set()

    # ---- 查询与停止 ----

    def snapshot(self) -> list[ConvView]:
        pending = pending_counts(self._convs)
        return [
            ConvView(
                conv, self._keys.get(conv), tail[-1].text, tail[-1].sender_role,
                tail[-1].sent_at, pending[conv], waiting_since(tail),
            )
            for conv, tail in self._convs.items()
        ]

    def unread(self) -> int:
        return sum(pending_counts(self._convs).values())

    def stop(self) -> None:
        """让 run() 尽快返回 "shutdown"；真正的停止原因由调用方自己记。"""
        self._stopped = True
        self._wake.set()

    # ---- 循环 ----

    async def run(self) -> StopReason:
        self._last_frame_at = self._clock()
        try:
            try:
                return await self._loop()
            finally:
                await self._save_unsaved()
        except Exception as e:  # noqa: BLE001 - 异常信息可能含消息内容，只记类型
            log.warning("im.session_failed", shop_id=self._shop_id, error=type(e).__name__)
            return "page_closed" if self._page.closed else "error"
        finally:
            self._publish_unread()  # 去抖中还没发出的数量
            self._publish_wait(0, 0)  # 停了就不再声称有人在等

    async def _loop(self) -> StopReason:
        while True:
            self._wake.clear()
            await self._save_unsaved()
            if self._stopped:
                return "shutdown"
            if self._page.closed:
                return "page_closed"
            if reason := await self._reload_if_needed():
                return reason
            self._publish_due()
            await self._wait(self._next_wait())

    async def _wait(self, seconds: float) -> None:
        """等到被回调触发，或睡满 seconds。"""
        tasks = [
            asyncio.ensure_future(self._sleep(seconds)),
            asyncio.ensure_future(self._wake.wait()),
        ]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()

    def _next_wait(self) -> float:
        if not self._dirty or self._quiet_until is None:
            return WAIT_TICK_S
        return min(WAIT_TICK_S, (self._quiet_until - self._clock()).total_seconds())

    async def _reload_if_needed(self) -> StopReason | None:
        """版本过低或长时间无帧时刷新页面；超出限额返回停止原因。"""
        now = self._clock()
        version_low = self._version_low
        if not version_low and now - self._last_frame_at < timedelta(seconds=POLL_S):
            return None
        if not may_act(
            self._reload_history, now, min_gap=RELOAD_MIN_GAP, per_day=RELOAD_PER_DAY
        ):
            return "version_low" if version_low else "error"
        self._version_low = False  # 先清：刷新过程中页面可能又报版本过低
        self._reload_history.append(now)
        log.info("im.reload", shop_id=self._shop_id, version_low=version_low)
        await self._page.reload()
        self._last_frame_at = self._clock()
        return None

    # ---- 消息与事件 ----

    def _absorb(self, msgs: list[Message]) -> list[Message]:
        """按 message_id 去重并追加到各会话尾部，返回新的那些。"""
        fresh: list[Message] = []
        for message in msgs:
            if message.message_id not in self._seen:
                self._seen.add(message.message_id)
                self._convs.setdefault(message.conversation_id, []).append(message)
                fresh.append(message)
        for conv in {m.conversation_id for m in fresh}:
            self._convs[conv].sort(key=lambda m: m.sent_at)  # 稳定排序：同一秒按到达先后
            del self._convs[conv][:-CONV_TAIL]
        return fresh

    async def _save_unsaved(self) -> None:
        while self._unsaved:
            batch, self._unsaved = self._unsaved, []
            await self._save(batch)

    def _publish_due(self) -> None:
        """前沿 + 尾沿去抖：发出过事件后 DEBOUNCE_S 内的新消息攒到期满一起发。"""
        now = self._clock()
        if self._dirty and self._quiet_until is not None and now < self._quiet_until:
            return
        waits = {conv: waiting_since(tail) for conv, tail in self._convs.items()}
        sent_unread = self._publish_unread()
        sent_wait = self._publish_wait(
            sum(since is not None for since in waits.values()), overdue_count(waits, now)
        )
        if self._dirty and (sent_unread or sent_wait):
            self._quiet_until = now + timedelta(seconds=DEBOUNCE_S)
        self._dirty = False

    def _publish_unread(self) -> bool:
        unread = self.unread()
        if unread == self._sent_unread and not self._new:
            return False
        self._events.publish(
            IM_UNREAD_CHANGED, {"shop_id": self._shop_id, "unread": unread, "new": self._new}
        )
        self._sent_unread, self._new = unread, 0
        return True

    def _publish_wait(self, waiting: int, overdue: int) -> bool:
        if (waiting, overdue) == self._sent_wait:
            return False
        self._events.publish(
            IM_WAIT_CHANGED, {"shop_id": self._shop_id, "waiting": waiting, "overdue": overdue}
        )
        self._sent_wait = (waiting, overdue)
        return True
