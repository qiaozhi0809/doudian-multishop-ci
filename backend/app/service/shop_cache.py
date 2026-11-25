"""按店的短时缓存：页面加载、切页、多标签页都会取计数，60 秒内每店最多请求平台一次。

只缓存成功结果（失败的下次重试）；同步完成后由调用方 invalidate，保证同步后马上看到新数。
缓存放在进程内存里：本服务是出单机上的单进程，重启后自然重建，不需要 Redis 之类。
"""

from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from app.service.shop_fanout import Job, ShopResult, fan_out
from app.service.shop_runner import ShopRunner

DEFAULT_TTL = timedelta(seconds=60)


class ShopTtlCache[T]:
    def __init__(self, clock: Callable[[], datetime], ttl: timedelta = DEFAULT_TTL) -> None:
        self._clock = clock
        self._ttl = ttl
        self._entries: dict[int, tuple[datetime, T]] = {}

    def invalidate(self, shop_id: int) -> None:
        self._entries.pop(shop_id, None)

    def _fresh(self, shop_id: int) -> tuple[datetime, T] | None:
        entry = self._entries.get(shop_id)
        if entry and self._clock() - entry[0] < self._ttl:
            return entry
        return None

    async def fan_out(
        self, shop_ids: Sequence[int], runner: ShopRunner, actor: str, job: Job, *, event: str,
    ) -> list[tuple[ShopResult, datetime | None]]:
        """和 fan_out 一样每店一条结果（顺序不变），附上数据取自平台的时间。

        缓存命中的店不请求平台。
        """
        hits = {i: e for i in shop_ids if (e := self._fresh(i)) is not None}
        misses = [i for i in shop_ids if i not in hits]
        fetched = {r.shop_id: r for r in await fan_out(misses, runner, actor, job, event=event)}
        now = self._clock()
        out: list[tuple[ShopResult, datetime | None]] = []
        for shop_id in shop_ids:
            if shop_id in hits:
                at, data = hits[shop_id]
                out.append((ShopResult(shop_id, True, data), at))
                continue
            result = fetched[shop_id]
            if result.ok:
                self._entries[shop_id] = (now, result.data)
            out.append((result, now if result.ok else None))
        return out
