"""飞鸽常驻页生命周期：选店、关卡、全局名额、经 ShopRunner 启动、退避重试、让出资料目录。

每家店一个后台任务：过关卡 → 拿名额 → 在该店队列里经登记表打开页面 → 跑只读会话 →
关页面、还名额、记审计 → 按退避再来一轮。页面在启动任务返回后继续常驻，会话结束才关。
消息正文只进内存与 im_message 表，不进日志、审计、事件。
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path

import structlog
from sqlalchemy import Engine

from app.adapter.browser.browser_registry import BrowserRegistry, CloseReason, Purpose
from app.adapter.browser.cloak_launch import CloakUnavailable
from app.adapter.browser.login import playwright_proxy
from app.adapter.doudian.errors import EgressUnavailable
from app.adapter.flybird.page import ImPage
from app.domain.audit import CallRecord
from app.domain.im_rules import ImState, StopReason, block_reason
from app.service import im_focus, im_history
from app.service.events import IM_STOPPED, IM_WAIT_CHANGED, SHOP_STATUS_CHANGED, EventBus
from app.service.im_focus import FocusResult
from app.service.im_run import Run
from app.service.im_session import ConvView, ImSession
from app.service.im_shop import ImStatus, ShopSlot
from app.service.periodic import SYSTEM_ACTOR, active_shop_ids
from app.service.shop_runner import ShopRunner
from app.store import audit_store, shop_store

log = structlog.get_logger()

SHUTDOWN_WAIT_S = 20  # 关机时等各店自行收尾的上限，超时取消
_QUEUE_SIZE = 1000  # 订阅队列：批量任务的进度事件多，别把状态事件挤掉
_HISTORY_SPAN = timedelta(days=1)  # 启动时读回多久的消息来恢复待回复与等待计时
_START_LIMITED = "今日启动次数已达上限"
_NO_PROXY = "该店没有可用的代理，不打开飞鸽页面"
_FAILURES: frozenset[StopReason] = frozenset({"error", "version_low", "page_closed"})
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ImWatcher:
    def __init__(
        self, engine: Engine, runner: ShopRunner, events: EventBus, browsers: BrowserRegistry,
        *, profiles_dir: Path, max_browsers: int,
        clock: Callable[[], datetime] = _utc_now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        attach: Callable[..., Awaitable[ImPage]] = ImPage.attach,
    ) -> None:
        self._engine = engine
        self._runner = runner
        self._events = events
        self._browsers = browsers
        self._profiles_dir = profiles_dir
        self._slots = asyncio.Semaphore(max_browsers)
        self._clock = clock
        self._sleep = sleep
        self._attach = attach
        self._shops: dict[int, ShopSlot] = {}
        self._reconciles: set[asyncio.Task] = set()
        self._closing = False

    # ---- 查询 ----

    def im_shop_ids(self) -> list[int]:
        """应接收飞鸽消息的店：active、未暂停、开关开着。"""
        with self._engine.connect() as conn:
            enabled = {s["id"] for s in shop_store.list(conn) if s["im_enabled"]}
        return [i for i in active_shop_ids(self._engine) if i in enabled]

    def status(self, shop_id: int) -> ImStatus:
        if (shop := self._shops.get(shop_id)) is not None:
            return replace(shop.status)
        return ImStatus(shop_id, self._blocked(shop_id) or "stopped", self._now_iso())

    def statuses(self) -> list[ImStatus]:
        return [replace(shop.status) for shop in self._shops.values()]

    def snapshot(self, shop_id: int) -> list[ConvView]:
        run = self._receiving(shop_id)
        return run.session.snapshot() if run else []

    def page(self, shop_id: int) -> ImPage | None:
        run = self._receiving(shop_id)
        return run.page if run else None

    # ---- 控制 ----

    async def start(self, shop_id: int, *, actor: str, offscreen: bool = True) -> ImStatus:
        """过关卡则在后台启动，不等页面打开；已在运行或在等重试时什么都不做。"""
        shop = self._shop(shop_id)
        async with shop.lock:
            self._launch(shop, actor, offscreen)
        return replace(shop.status)

    async def stop(self, shop_id: int, *, reason: StopReason, actor: str) -> None:
        """结束该店的页面与重试，返回时浏览器已关。"""
        shop = self._shop(shop_id)
        async with shop.lock:
            await self._halt(shop, reason, actor)

    async def restart(self, shop_id: int, *, actor: str) -> ImStatus:
        """手动「重新连接」：清零退避计数后重开，仍走全部关卡。"""
        shop = self._shop(shop_id)
        async with shop.lock:
            await self._halt(shop, "preempted", actor)
            shop.retry.reset()
            shop.status.last_error = None
            self._launch(shop, actor, True)
        return replace(shop.status)

    async def reconcile(self, shop_id: int) -> None:
        """按店铺现状开或停。在等重试的不提前启动；需重新连接的只等手动处理。"""
        shop = self._shop(shop_id)
        async with shop.lock:
            if self._blocked(shop_id):
                await self._halt(shop, "ineligible", SYSTEM_ACTOR)
            elif shop.status.state != "needs_refresh":
                self._launch(shop, SYSTEM_ACTOR, True)

    async def yield_profile(self, shop_id: int) -> bool:
        """让出该店资料目录：关掉常驻页，之后按退避重开。没有常驻页返回 False。

        扫码与抓取在该店队列里调用，所以这里只能等不需要该店队列的收尾动作。
        """
        shop = self._shops.get(shop_id)
        run = shop.run if shop else None
        if run is None or not run.opened:
            return False
        run.stop_reason = run.stop_reason or "preempted"
        await self._browsers.close_shop(shop_id, CloseReason.PREEMPTED)
        run.request_stop(run.stop_reason)
        await run.done.wait()
        return True

    async def run(self, bus: EventBus, stop: asyncio.Event) -> None:
        """启动选中的店，之后按店铺状态事件开停，直到 stop 置位。关页面由 shutdown() 负责。"""
        async with bus.subscribe(_QUEUE_SIZE) as sub:
            self._clear_waits()
            for shop_id in self.im_shop_ids():
                await self.start(shop_id, actor=SYSTEM_ACTOR)
            stopper = asyncio.ensure_future(stop.wait())
            try:
                while not stop.is_set():
                    getter = asyncio.ensure_future(anext(sub))
                    await asyncio.wait({getter, stopper}, return_when=asyncio.FIRST_COMPLETED)
                    if not getter.done():
                        getter.cancel()
                        break
                    event, data = getter.result()
                    if event == SHOP_STATUS_CHANGED:
                        self._spawn_reconcile(int(data["shop_id"]))
            finally:
                stopper.cancel()

    async def shutdown(self) -> None:
        """结束全部会话、关掉各自的页面、取消重试；之后不再启动。"""
        self._closing = True
        for task in self._reconciles:
            task.cancel()
        shops = list(self._shops.values())
        halts = (self._halt(shop, "shutdown", SYSTEM_ACTOR) for shop in shops)
        try:
            await asyncio.wait_for(asyncio.gather(*halts), SHUTDOWN_WAIT_S)
        except TimeoutError:  # 页面迟迟打不开或关不掉：取消，浏览器由上下文与登记表收尾
            log.warning("im.shutdown_timeout")
            tasks = [shop.task for shop in shops if shop.task is not None]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for shop in shops:
                self._set(shop, self._blocked(shop.id) or "stopped")

    async def focus(self, shop_id: int, conversation_id: str, *, actor: str) -> FocusResult:
        """「在飞鸽中回复」：置前该店常驻页窗口并点开会话一次（im_focus）。"""
        return await im_focus.open_conversation(
            self._engine, self._runner, shop_id, conversation_id,
            receiving=partial(self._receiving, shop_id), actor=actor, now=self._now_iso)

    def purge_messages(self, now: datetime) -> int:
        """删除超过保留期的飞鸽消息（每日清理调用）。"""
        return im_history.purge(self._engine, now)

    # ---- 一家店的循环 ----

    def _launch(self, shop: ShopSlot, actor: str, offscreen: bool) -> None:
        if self._closing or (shop.task is not None and not shop.task.done()):
            return
        if blocked := self._blocked(shop.id):
            self._set(shop, blocked)
            return
        self._set(shop, "queued" if self._slots.locked() else "starting")
        shop.task = asyncio.create_task(self._drive(shop, actor, offscreen))

    async def _halt(self, shop: ShopSlot, reason: StopReason, actor: str) -> None:
        if (run := shop.run) is not None and run.committed:  # 让这一轮自己收尾
            run.halted, run.stop_actor = True, actor
            run.request_stop(reason)
            await run.done.wait()
        if (task := shop.task) is not None:  # 还在排队，或在等下次重试
            task.cancel()
            await asyncio.wait([task])
            shop.task = None
        self._set(shop, self._blocked(shop.id) or "stopped")

    async def _drive(self, shop: ShopSlot, actor: str, offscreen: bool) -> None:
        try:
            while (delay := await self._cycle(shop, actor, offscreen)) is not None:
                await self._sleep(delay)
                actor = SYSTEM_ACTOR
        except Exception as e:  # noqa: BLE001 - 库错误信息可能带参数，只记类型
            log.warning("im.watch_failed", shop_id=shop.id, error=type(e).__name__)
            shop.status.last_error = type(e).__name__
            self._set(shop, "stopped")

    async def _cycle(self, shop: ShopSlot, actor: str, offscreen: bool) -> float | None:
        """跑一轮；返回多久后再来一轮，None 表示不再自动重试。"""
        if blocked := self._blocked(shop.id):
            self._set(shop, blocked)
            return None
        if (wait := shop.retry.wait_for_start(self._clock())) is not None:
            shop.status.last_error = _START_LIMITED
            self._back_off(shop, wait)
            return wait
        run = shop.run = Run(actor)
        try:
            if self._slots.locked():
                self._set(shop, "queued")
            async with self._slots:
                try:
                    result = await self._receive(shop, run, offscreen)
                finally:
                    await run.close()
            return self._settle(shop, run, result)
        finally:
            shop.run = None
            run.done.set()

    async def _receive(self, shop: ShopSlot, run: Run, offscreen: bool) -> StopReason:
        self._set(shop, "starting")
        try:
            await self._runner.run(
                shop.id, lambda _client: self._open(shop, run, offscreen), actor=run.actor)
            if run.session is None:  # 开页前后发现不该开了
                return "ineligible"
            return await run.session.run()
        except Exception as e:  # noqa: BLE001 - 任何启动失败都按退避重试
            if not run.stopping:
                # CloakUnavailable 的消息面向用户；其他异常信息可能带地址，只记类型
                error = str(e) if isinstance(e, CloakUnavailable) else type(e).__name__
                shop.status.last_error = error
                log.warning("im.start_failed", shop_id=shop.id, error=type(e).__name__)
            return "error"

    async def _open(self, shop: ShopSlot, run: Run, offscreen: bool) -> None:
        """在该店队列里打开页面并建好会话；返回后页面继续常驻。"""
        run.committed = True
        if self._blocked(shop.id):  # 排队期间开关或状态变了
            return
        proxy = self._runner.proxy_for(shop.id)
        if proxy is None and self._shop_row(shop.id)["egress_mode"] != "direct":
            raise EgressUnavailable(_NO_PROXY)  # 绝不把缺代理当成直连
        since = (self._clock() - _HISTORY_SPAN).strftime(_ISO_FMT)
        history = await asyncio.to_thread(im_history.load_since, self._engine, shop.id, since)
        if run.stopping:
            return
        shop.retry.record_start(self._clock())
        context = await run.open(self._browsers.open_cloak(
            self._profiles_dir / str(shop.id), Purpose.IM, playwright_proxy(proxy),
            offscreen=offscreen, on_close=run.closed_by_registry))
        if run.stopping:  # 启动途中要求停（如风控暂停）：不再打开工作台
            return
        try:
            page = await self._attach(
                context, on_frame=run.relay.on_frame, on_list=run.relay.on_list,
                on_messages=run.relay.on_messages)
        except BaseException:
            await run.close()  # 趁还占着该店队列关掉，下一个任务拿到的是空目录
            raise
        if run.stopping:
            return
        run.page = page
        run.session = ImSession(
            shop.id, page, self._events, clock=self._clock, sleep=self._sleep,
            reload_history=shop.retry.reload_history,
            save_messages=partial(self._save, shop.id), history=history)
        run.relay.connect(run.session)
        run.started_at = self._clock()
        shop.status.last_error = None
        self._set(shop, "running")
        self._audit(shop.id, "im.start", run.actor, "", run, "ok")

    def _settle(self, shop: ShopSlot, run: Run, result: StopReason) -> float | None:
        """页面已关、名额已还：写审计，定下状态与下次重试。"""
        reason = run.close_reason or run.stop_reason or result
        outcome = "error" if reason in _FAILURES else "ok"
        if run.session is not None:
            self._audit(shop.id, "im.stop", run.stop_actor, reason, run, outcome)
        elif outcome == "error":
            self._audit(shop.id, "im.start", run.actor, reason, run, outcome)
        if not (run.halted or self._closing):
            ran = self._clock() - run.started_at if run.started_at else timedelta(0)
            if (delay := shop.retry.delay_after(reason, ran)) is not None:
                self._back_off(shop, delay)
                return delay
            if reason == "version_low":
                self._set(shop, "needs_refresh")
                self._events.publish(IM_STOPPED, {"shop_id": shop.id, "state": "needs_refresh"})
                return None
        self._set(shop, self._blocked(shop.id) or "stopped")
        return None

    # ---- 内部 ----

    def _shop(self, shop_id: int) -> ShopSlot:
        if shop_id not in self._shops:
            self._shops[shop_id] = ShopSlot(ImStatus(shop_id, "stopped", self._now_iso()))
        return self._shops[shop_id]

    def _receiving(self, shop_id: int) -> Run | None:
        shop = self._shops.get(shop_id)
        run = shop.run if shop else None
        return run if run and run.opened and run.session else None

    def _set(self, shop: ShopSlot, state: ImState, retry_at: datetime | None = None) -> None:
        status = shop.status
        if status.state != state:
            status.state, status.since = state, self._now_iso()
        status.next_retry_at = retry_at.strftime(_ISO_FMT) if retry_at else None

    def _back_off(self, shop: ShopSlot, seconds: float) -> None:
        self._set(shop, "backoff", self._clock() + timedelta(seconds=seconds))

    def _now_iso(self) -> str:
        return self._clock().strftime(_ISO_FMT)

    def _shop_row(self, shop_id: int):
        with self._engine.connect() as conn:
            return shop_store.get(conn, shop_id)

    def _blocked(self, shop_id: int) -> ImState | None:
        row = self._shop_row(shop_id)
        return "off" if row is None else block_reason(row, None)

    def _spawn_reconcile(self, shop_id: int) -> None:
        # 另起任务：停一家店要等它的页面关完，不能挡住别店的事件
        task = asyncio.create_task(self.reconcile(shop_id))
        self._reconciles.add(task)
        task.add_done_callback(self._reconciled)

    def _reconciled(self, task: asyncio.Task) -> None:
        self._reconciles.discard(task)
        if not task.cancelled() and (error := task.exception()) is not None:
            log.warning("im.reconcile_failed", error=type(error).__name__)

    def _clear_waits(self) -> None:
        """进程刚启动时没有任何店在接收：收起上次异常退出留下的「超时未回复」。"""
        with self._engine.connect() as conn:
            shop_ids = [s["id"] for s in shop_store.list(conn)]
        for shop_id in shop_ids:
            self._events.publish(
                IM_WAIT_CHANGED, {"shop_id": shop_id, "waiting": 0, "overdue": 0})

    async def _save(self, shop_id: int, msgs) -> None:
        await im_history.save(self._engine, shop_id, msgs, self._now_iso())

    def _audit(
        self, shop_id: int, action: str, actor: str, reason: str, run: Run, result: str
    ) -> None:
        summary = {"reason": reason, "read_blocked": run.read_blocked}
        with self._engine.begin() as conn:
            audit_store.insert(
                conn, CallRecord(shop_id, action, actor, {}, summary, result, 0), self._now_iso())
