"""进程内事件总线：每个订阅者一个有界队列，满了丢最旧，发布方永不阻塞。"""

import asyncio
from typing import Any, Literal

import structlog

log = structlog.get_logger()

SHOP_STATUS_CHANGED = "shop_status_changed"
SHOP_LOGIN_FAILED = "shop_login_failed"
SYNC_PROGRESS = "sync_progress"
LABEL_PROGRESS = "label_progress"  # 逐单执行结果（成功 / 失败 / 待核实 / 跳过）
LABEL_DONE = "label_done"  # 一个预览的执行结束汇总
PRINT_PROGRESS = "print_progress"  # 逐单打印结果（成功 / 失败 / 转手动补打）
PRINT_DONE = "print_done"  # 一个打印批次的结束汇总
SHIP_PROGRESS = "ship_progress"  # 逐单发货结果（成功 / 失败 / 跳过）
SHIP_DONE = "ship_done"  # 一个发货批次的结束汇总
RECONCILE_DONE = "reconcile_done"  # 一次对账的结束汇总
SHIP_DEADLINE_WARNING = "ship_deadline_warning"  # 临近发货超时的订单（ENG-07）
# 一轮订单同步新入库的单数 {shop_id, count}：有基线才发；部分 / 中途失败的同步也报已入库的
ORDERS_NEW = "orders_new"
# 一轮售后同步新入库且属待办的单数 {shop_id, count}：同上，有基线才发，部分同步也报
AFTERSALES_NEW = "aftersales_new"
SYNC_RESULT = "sync_result"  # 手动同步一店结束 {kind, shop_id, ok, error}；定时同步不发
NOTIFICATION = "notification"  # 通知新增 / 更新 / 恢复 / 已读

DEFAULT_QUEUE_SIZE = 100

Event = tuple[str, dict[str, Any]]


class Subscription:
    """订阅句柄：可 `async for` 迭代，`close()` 或 `async with` 退出时取消订阅。"""

    def __init__(self, bus: "EventBus", queue: asyncio.Queue[Event]) -> None:
        self._bus = bus
        self._queue = queue

    def __aiter__(self) -> "Subscription":
        return self

    async def __anext__(self) -> Event:
        return await self._queue.get()

    def close(self) -> None:
        self._bus._remove(self._queue)

    async def __aenter__(self) -> "Subscription":
        return self

    async def __aexit__(self, *_: object) -> None:
        self.close()


class EventBus:
    def __init__(self, queue_size: int = DEFAULT_QUEUE_SIZE) -> None:
        self._queue_size = queue_size
        # (队列, 订阅时所在的事件循环)；循环为 None 表示订阅发生在循环之外
        self._subs: list[tuple[asyncio.Queue[Event], asyncio.AbstractEventLoop | None]] = []

    @property
    def subscriber_count(self) -> int:
        return len(self._subs)

    def subscribe(self, queue_size: int | None = None) -> Subscription:
        queue: asyncio.Queue[Event] = asyncio.Queue(queue_size or self._queue_size)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        self._subs.append((queue, loop))
        return Subscription(self, queue)

    def _remove(self, queue: asyncio.Queue[Event]) -> None:
        self._subs = [(q, loop) for q, loop in self._subs if q is not queue]

    @staticmethod
    def _put(queue: asyncio.Queue[Event], item: Event) -> None:
        if queue.full():
            dropped, _ = queue.get_nowait()
            log.warning("events.dropped", dropped_event=dropped)  # 只记事件名，不记内容
        queue.put_nowait(item)

    def publish(self, event: str, data: dict[str, Any]) -> None:
        """可在事件循环线程或工作线程调用；跨线程时经 call_soon_threadsafe 转回订阅者的循环。"""
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        for queue, loop in list(self._subs):
            if loop is None or loop is current:
                self._put(queue, (event, data))
            elif not loop.is_closed():
                loop.call_soon_threadsafe(self._put, queue, (event, data))


SyncKind = Literal["orders", "aftersales", "products", "stock", "fund"]


def publish_sync_result(
    events: EventBus | None, kind: SyncKind, shop_id: int, error: str | None,
) -> None:
    """手动同步一店结束：成功 error=None；失败带面向用户的原因。"""
    if events is not None:
        events.publish(SYNC_RESULT, {
            "kind": kind, "shop_id": shop_id, "ok": error is None, "error": error})
