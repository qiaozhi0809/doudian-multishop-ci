"""飞鸽生命周期测试的假件与环境：真登记表（假浏览器进程）、真会话、虚拟时钟。数据全部虚构。

假登记表只换掉「启动浏览器」这一步，登记、关闭、on_close 的语义用真实现。
"""

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlalchemy as sa

from app.adapter.browser.browser_registry import BrowserRegistry, Purpose
from app.adapter.browser.login import LoginResult
from app.adapter.flybird import read_guard
from app.service.events import IM_STOPPED, IM_WAIT_CHANGED
from app.service.im_watcher import ImWatcher
from app.store import im_message_store, shop_store
from tests.fakes import NullProcesses
from tests.service.im_session_test import START, FakeTime
from tests.service.support import NOW, Env

IM_PROXY = "http://u:p@127.0.0.1:9"
ADMIN = "admin"
LOGIN = LoginResult(
    [{"name": "sessionid", "value": "v", "domain": ".jinritemai.com", "path": "/"}],
    "tok_" + "y" * 8, "2027-01-24T00:00:00Z", {"User-Agent": "UA/1"},
)


class _AbortableRoute:
    async def abort(self) -> None:
        pass


class FakeContext:
    def __init__(self) -> None:
        self.closed = False
        self._listeners: list[Callable[[object], None]] = []
        self._routes: list[Callable[[Any], Any]] = []

    async def add_init_script(self, script: str | None = None) -> None:
        pass

    async def route(self, _pattern: str, handler: Callable[[Any], Any]) -> None:
        self._routes.append(handler)

    async def mark_read(self) -> None:
        """页面发出一次 HTTP 已读请求：走真实的拦截处理函数。"""
        for handler in self._routes:
            await handler(_AbortableRoute())

    def on(self, event: str, listener: Callable[[object], None]) -> None:
        assert event == "close"
        self._listeners.append(listener)

    async def close(self) -> None:
        if not self.closed:
            self.closed = True
            for listener in self._listeners:
                listener(self)


@dataclass
class OpenCall:
    profile_dir: Path
    purpose: Purpose
    proxy: dict | None
    kwargs: dict[str, Any]
    context: FakeContext | None = None
    on_close: Callable[[str], None] | None = None


class FakeRegistry(BrowserRegistry):
    def __init__(self) -> None:
        super().__init__(NullProcesses())
        self.opened: list[OpenCall] = []
        self.closed_shops: list[tuple[int, str]] = []
        self.launch_error: Exception | None = None
        self.launch_gate: asyncio.Event | None = None  # 设了就卡在启动途中

    def open_cloak(self, profile_dir, purpose, proxy, **kwargs):
        call = OpenCall(profile_dir, purpose, proxy, kwargs, on_close=kwargs.get("on_close"))
        self.opened.append(call)

        async def launch() -> FakeContext:
            if self.launch_gate is not None:
                await self.launch_gate.wait()
            if self.launch_error is not None:
                raise self.launch_error
            call.context = FakeContext()
            return call.context

        return self.open(profile_dir, purpose, launch, on_close=kwargs.get("on_close"))

    async def close_shop(self, shop_id: int, reason: str = "preempted") -> bool:
        self.closed_shops.append((shop_id, reason))
        return await super().close_shop(shop_id, reason)

    def open_contexts(self) -> list[FakeContext]:
        return [c.context for c in self.opened if c.context and not c.context.closed]


class FakeImPage:
    def __init__(self, context: FakeContext, on_frame, on_list, on_messages) -> None:
        self.context = context
        self.on_frame = on_frame
        self.on_list = on_list
        self.on_messages = on_messages
        self.reloads = 0

    @property
    def closed(self) -> bool:
        return self.context.closed

    async def reload(self) -> None:
        self.reloads += 1


class FakeAttach:
    def __init__(self) -> None:
        self.pages: list[FakeImPage] = []
        self.error: Exception | None = None
        self.gate: asyncio.Event | None = None  # 设了就卡在打开页面途中
        self.during: Callable[[FakeImPage], None] | None = None  # 返回前页面已经收到的东西

    async def __call__(self, context, *, on_frame, on_list, on_messages) -> FakeImPage:
        await read_guard.install(context)  # 与 ImPage.attach 一样，先装拦截
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error
        page = FakeImPage(context, on_frame, on_list, on_messages)
        self.pages.append(page)
        if self.during is not None:
            self.during(page)
        return page


async def until(condition: Callable[[], object], timeout: float = 2.0) -> None:
    """存库走工作线程，让出事件循环不够：按真实时间轮询到条件成立。"""
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "条件一直不成立"
        await asyncio.sleep(0.001)


async def drain() -> None:
    """给后台任务（含工作线程）一点时间，用于断言「什么都没发生」。"""
    for _ in range(10):
        await asyncio.sleep(0.002)


class Rig:
    """Env 的第一家店 + 按需加店；全部默认开启飞鸽。"""

    def __init__(self, engine, tmp_path, *, max_browsers: int = 3) -> None:
        self.env = Env(engine, tmp_path)
        self.env.egress.proxy = IM_PROXY
        self.engine = engine
        self.events = self.env.events
        self.published: list[tuple[str, dict]] = []
        publish = self.events.publish

        def record(event: str, data: dict) -> None:
            self.published.append((event, data))
            publish(event, data)

        self.events.publish = record
        self.time = FakeTime()
        self.registry = FakeRegistry()
        self.attach = FakeAttach()
        self.profiles = tmp_path / "profiles"
        self.watcher = ImWatcher(
            engine, self.env.runner, self.events, self.registry, profiles_dir=self.profiles,
            max_browsers=max_browsers, clock=self.time.clock, sleep=self.time.sleep,
            attach=self.attach,
        )
        self.shop_id = self.env.shop_id
        self.update(self.shop_id, im_enabled=1)

    # ---- 店铺 ----

    def add_shop(self, *, enabled: bool = True) -> int:
        with self.engine.begin() as conn:
            shop_id = shop_store.create(conn, f"测试小铺{len(shop_store.list(conn))}", NOW)
        self.env.sessions.save_login(shop_id, LOGIN)
        if enabled:
            self.update(shop_id, im_enabled=1)
        return shop_id

    def update(self, shop_id: int, **fields) -> None:
        with self.engine.begin() as conn:
            shop_store.update_fields(conn, shop_id, NOW, **fields)

    def set_status(self, shop_id: int, status: str) -> None:
        with self.engine.begin() as conn:
            shop_store.set_status(conn, shop_id, status, NOW)

    def set_egress(self, shop_id: int, **fields) -> None:
        with self.engine.begin() as conn:
            shop_store.set_egress(conn, shop_id, NOW, **fields)

    def pause(self, shop_id: int) -> None:
        with self.engine.begin() as conn:
            shop_store.set_paused(conn, shop_id, "risk_blocked:test", NOW)

    # ---- 观察 ----

    def state(self, shop_id: int | None = None) -> str:
        return self.watcher.status(shop_id or self.shop_id).state

    async def wait_state(self, state: str, shop_id: int | None = None) -> None:
        await until(lambda: self.state(shop_id) == state)

    async def start(self, shop_id: int | None = None, *, wait: str = "running") -> None:
        await self.watcher.start(shop_id or self.shop_id, actor=ADMIN)
        await self.wait_state(wait, shop_id)

    async def advance(self, seconds: float) -> None:
        await self.time.advance(seconds)
        await drain()

    @property
    def now(self):
        return self.time.now

    def elapsed(self) -> float:
        return (self.time.now - START).total_seconds()

    def audits(self, action: str) -> list[dict]:
        with self.engine.connect() as conn:
            rows = conn.execute(sa.text(
                "SELECT shop_id, actor, result, req_summary, resp_summary FROM audit_log"
                " WHERE action = :a ORDER BY id"), {"a": action}).mappings()
            return [{**r, "resp": json.loads(r["resp_summary"] or "{}")} for r in rows]

    def messages(self, shop_id: int | None = None) -> list[dict]:
        with self.engine.connect() as conn:
            return im_message_store.recent_for_shop(conn, shop_id or self.shop_id, "")

    def stopped_events(self) -> list[dict]:
        return [data for event, data in self.published if event == IM_STOPPED]

    def wait_events(self) -> list[dict]:
        return [data for event, data in self.published if event == IM_WAIT_CHANGED]
