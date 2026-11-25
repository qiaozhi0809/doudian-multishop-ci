"""同店串行、全局限流：每店一把锁，全局同时最多 N 个店在跑。"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")

DEFAULT_MAX_CONCURRENT_SHOPS = 3


class ShopScheduler:
    def __init__(self, max_concurrent_shops: int = DEFAULT_MAX_CONCURRENT_SHOPS) -> None:
        self._global = asyncio.Semaphore(max_concurrent_shops)
        self._locks: dict[int, asyncio.Lock] = {}

    async def run(self, shop_id: int, job: Callable[[], Awaitable[T]]) -> T:
        """先拿店锁再拿全局名额：同店排队的任务不占用全局名额。"""
        lock = self._locks.setdefault(shop_id, asyncio.Lock())
        async with lock, self._global:
            return await job()
