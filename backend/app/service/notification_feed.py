"""事件翻译（通知中心 6.3）：订阅事件总线，把业务事件翻译成 NotificationService 调用。

店铺状态类一律按当前库里的店铺行对账（事件载荷各发布方不一致，只当「该店有变化」的信号）。
"""

import asyncio
from collections import Counter
from collections.abc import Callable
from typing import Any

import structlog
from sqlalchemy import Engine

from app.domain.notification_rules import Kind, batch_detail
from app.service.events import (
    AFTERSALES_NEW,
    LABEL_DONE,
    ORDERS_NEW,
    PRINT_DONE,
    RECONCILE_DONE,
    SHIP_DEADLINE_WARNING,
    SHIP_DONE,
    SHOP_LOGIN_FAILED,
    SHOP_STATUS_CHANGED,
    SYNC_RESULT,
    EventBus,
)
from app.service.notifications import NotificationService
from app.service.session_manager import DISABLED, NEEDS_LOGIN
from app.service.shop_runner import RISK_PAUSE_PREFIX
from app.store import notification_store, session_store, shop_store

log = structlog.get_logger()

# 订阅队列放大：逐单进度事件密集时，也不挤掉批次结束等关键事件
FEED_QUEUE_SIZE = 2000
_EGRESS_KINDS: dict[str, Kind] = {
    "unreachable": "egress_unreachable",
    "changed": "egress_changed",
    "duplicate": "egress_duplicate",
}
_DEADLINE_PREFIX = "deadline:"


class NotificationFeed:
    def __init__(self, engine: Engine, notifications: NotificationService) -> None:
        self._engine = engine
        self._n = notifications
        self._handlers: dict[str, Callable[[dict[str, Any]], None]] = {
            SHOP_STATUS_CHANGED: self._on_shop,
            SHOP_LOGIN_FAILED: self._on_shop,
            SHIP_DEADLINE_WARNING: self._on_deadline,
            LABEL_DONE: self._on_label_done,
            SHIP_DONE: lambda d: self._batch("ship", d),
            PRINT_DONE: lambda d: self._batch("print", d),
            RECONCILE_DONE: lambda _d: self._n.emit("reconcile_done", shop_id=None),
            ORDERS_NEW: lambda d: self._n.emit(
                "new_order", shop_id=d["shop_id"], count=d["count"]),
            AFTERSALES_NEW: lambda d: self._n.emit(
                "new_aftersale", shop_id=d["shop_id"], count=d["count"]),
            SYNC_RESULT: self._on_sync_result,
        }

    def handle(self, event: str, data: dict[str, Any]) -> None:
        handler = self._handlers.get(event)
        if handler is not None:
            handler(data)

    async def run(self, bus: EventBus, stop: asyncio.Event) -> None:
        """订阅循环：库操作放到工作线程；单个事件处理出错只记日志，循环不退出。"""
        sub = bus.subscribe(FEED_QUEUE_SIZE)
        stopper = asyncio.ensure_future(stop.wait())
        try:
            while not stop.is_set():
                getter = asyncio.ensure_future(anext(sub))
                await asyncio.wait({getter, stopper}, return_when=asyncio.FIRST_COMPLETED)
                if not getter.done():
                    getter.cancel()
                    break
                event, data = getter.result()
                if event not in self._handlers:
                    continue
                try:
                    await asyncio.to_thread(self.handle, event, data)
                except Exception:
                    log.exception("notification_feed.failed", notify_event=event)
        finally:
            stopper.cancel()
            sub.close()

    # ---- 店铺状态对账 ----

    def _on_shop(self, data: dict[str, Any]) -> None:
        self.reconcile_shop(int(data["shop_id"]))

    def reconcile_shop(self, shop_id: int) -> None:
        with self._engine.connect() as conn:
            shop = shop_store.get(conn, shop_id)
            had_session = session_store.load(conn, shop_id) is not None
        if shop is None or shop["status"] == DISABLED:  # 已删除 / 停用：不再报该店问题
            for family in ("login", "egress", "risk"):
                self._n.resolve_state(family, shop_id=shop_id)
            return
        if shop["status"] == NEEDS_LOGIN and had_session:  # 从未登录过的新店不算失效
            self._n.raise_state("login", "login_expired", shop_id=shop_id)
        else:
            self._n.resolve_state("login", shop_id=shop_id)
        egress_kind = _EGRESS_KINDS.get(shop["egress_status"] or "")
        if egress_kind is not None:
            self._n.raise_state("egress", egress_kind, shop_id=shop_id)
        else:
            self._n.resolve_state("egress", shop_id=shop_id)
        reason = shop["paused_reason"] or ""
        if reason.startswith(RISK_PAUSE_PREFIX):
            self._n.raise_state(
                "risk", "risk_paused", shop_id=shop_id,
                detail=reason.removeprefix(RISK_PAUSE_PREFIX) or None)
        else:
            self._n.resolve_state("risk", shop_id=shop_id)

    # ---- 临近发货超时 ----

    def _on_deadline(self, data: dict[str, Any]) -> None:
        per_shop = Counter(int(i["shop_id"]) for i in data.get("items") or [])
        for shop_id, n in per_shop.items():
            self._n.raise_state("deadline", "ship_deadline", shop_id=shop_id, count=n)
        with self._engine.connect() as conn:
            open_ids = {
                int(r["shop_id"]) for r in notification_store.open_strong_states(conn)
                if (r["state_key"] or "").startswith(_DEADLINE_PREFIX)
            }
        for shop_id in sorted(open_ids - set(per_shop)):
            self._n.resolve_state("deadline", shop_id=shop_id)

    # ---- 批量结果 / 同步结果 ----

    def _on_label_done(self, data: dict[str, Any]) -> None:
        self._batch(str(data.get("mode") or "obtain"), data)

    def _batch(self, op: str, data: dict[str, Any]) -> None:
        if data.get("simulated"):  # 演练模式没有真实操作
            return
        failed = int(data.get("failed") or 0)
        self._n.emit(
            "batch_failed" if failed > 0 else "batch_done", shop_id=None,
            count=int(data.get("ok") or 0), detail=batch_detail(op, failed))

    def _on_sync_result(self, data: dict[str, Any]) -> None:
        self._n.emit(
            "sync_done" if data.get("ok") else "sync_failed",
            shop_id=int(data["shop_id"]), detail=str(data["kind"]))
