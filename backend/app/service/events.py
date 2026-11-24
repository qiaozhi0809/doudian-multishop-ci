"""进程内事件总线：每个订阅者一个有界队列，满了丢最旧，发布方永不阻塞。"""

import asyncio
from typing import Any

SHOP_STATUS_CHANGED = "shop_status_changed"
SHOP_LOGIN_FAILED = "shop_login_failed"
SYNC_PROGRESS = "sync_progress"

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
        self._queues: list[asyncio.Queue[Event]] = []

    @property
    def subscriber_count(self) -> int:
        return len(self._queues)

    def subscribe(self) -> Subscription:
        queue: asyncio.Queue[Event] = asyncio.Queue(self._queue_size)
        self._queues.append(queue)
        return Subscription(self, queue)

    def _remove(self, queue: asyncio.Queue[Event]) -> None:
        if queue in self._queues:
            self._queues.remove(queue)

    def publish(self, event: str, data: dict[str, Any]) -> None:
        for q in self._queues:
            if q.full():
                q.get_nowait()
            q.put_nowait((event, data))
