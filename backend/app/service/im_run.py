"""飞鸽常驻页的一轮（启动到停止）：持有浏览器上下文、页面、会话，记停止原因。"""

import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from datetime import datetime
from typing import Any

import structlog

from app.adapter.browser.browser_registry import CloseReason
from app.adapter.flybird import read_guard
from app.adapter.flybird.page import ImPage
from app.adapter.flybird.parse import ConvListResult, Message
from app.domain.im_rules import StopReason
from app.service.im_session import ImSession

log = structlog.get_logger()

# 登记表回传的关闭原因 → 停止原因；其余（进程没了等）都按页面关闭
_REASON_BY_CLOSE: dict[str, StopReason] = {
    CloseReason.EXPIRED: "lifetime",  # 每日重启
    CloseReason.PREEMPTED: "preempted",
    CloseReason.SHUTDOWN: "shutdown",
}


class PageRelay:
    """ImPage.attach 要先给回调，会话要页面有了才能建：先按到达顺序攒着，接上后补交再直接转发。"""

    def __init__(self) -> None:
        self._session: ImSession | None = None
        self._early: list[Callable[[ImSession], None]] = []

    def on_frame(self, raw: bytes) -> None:
        self._deliver(lambda session: session.on_frame(raw))

    def on_list(self, result: ConvListResult) -> None:
        self._deliver(lambda session: session.on_list(result))

    def on_messages(self, msgs: list[Message]) -> None:
        self._deliver(lambda session: session.on_messages(msgs))

    def connect(self, session: ImSession) -> None:
        for call in self._early:
            call(session)
        self._early.clear()
        self._session = session

    def _deliver(self, call: Callable[[ImSession], None]) -> None:
        if self._session is None:
            self._early.append(call)
        else:
            call(self._session)


class Run:
    def __init__(self, actor: str) -> None:
        self.actor = actor
        self.stop_actor = actor
        self.relay = PageRelay()
        self.done = asyncio.Event()  # 页面已关、名额已还、审计已写
        self.committed = False  # 已进入该店队列：页面可能开着，不能直接取消
        self.halted = False  # 被 stop() 要求结束：不再自动重试
        self.opened = False  # 浏览器上下文开着
        self.page: ImPage | None = None
        self.session: ImSession | None = None
        self.started_at: datetime | None = None  # 开始接收的时间
        self.stop_reason: StopReason | None = None  # 本系统决定的原因
        self.close_reason: StopReason | None = None  # 登记表回传的原因，优先
        self.blocked_before = read_guard.blocked_count()
        self._stack = AsyncExitStack()

    @property
    def stopping(self) -> bool:
        return self.stop_reason is not None or self.close_reason is not None

    @property
    def read_blocked(self) -> int:
        """本轮拦下的已读请求数。计数是进程级的，多店同时接收时会算进别店的。"""
        return read_guard.blocked_count() - self.blocked_before

    async def open(self, browser: AbstractAsyncContextManager[Any]) -> Any:
        """进入浏览器上下文并一直持有到 close()。"""
        self.blocked_before = read_guard.blocked_count()
        context = await self._stack.enter_async_context(browser)
        self.opened = True
        return context

    async def close(self) -> None:
        try:
            await self._stack.aclose()
        except Exception as e:  # noqa: BLE001 - 登记表负责强杀兜底，这里只记类型
            log.warning("im.close_failed", error=type(e).__name__)
        self.opened = False

    def request_stop(self, reason: StopReason) -> None:
        self.stop_reason = reason
        if self.session is not None:
            self.session.stop()

    def closed_by_registry(self, reason: str) -> None:
        """open_cloak 的 on_close。"""
        if reason == CloseReason.DONE:  # close() 自己退出上下文
            return
        self.close_reason = _REASON_BY_CLOSE.get(reason, "page_closed")
        if self.session is not None:
            self.session.stop()
