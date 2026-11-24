"""同店请求间隔：随机 0.3 ~ 1.2 秒。"""

import asyncio
import random
from collections.abc import Awaitable, Callable

MIN_GAP_S = 0.3
MAX_GAP_S = 1.2


class ShopPacer:
    def __init__(
        self,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rand: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self._sleep = sleep
        self._rand = rand

    async def wait(self) -> None:
        await self._sleep(self._rand(MIN_GAP_S, MAX_GAP_S))
