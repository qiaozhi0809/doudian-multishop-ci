"""定时任务：固定间隔循环、对所有可用店铺逐个执行（单店失败不影响其他店）。"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.service.session_manager import ACTIVE
from app.store import shop_store

log = structlog.get_logger()

ORDER_SYNC_INTERVAL_S = 300
PROBE_INTERVAL_S = 1800
SYSTEM_ACTOR = "system"


async def run_every(
    interval_s: float, fn: Callable[[], Awaitable[Any]], stop: asyncio.Event
) -> None:
    """立即执行一次，之后每隔 interval_s 执行；fn 抛异常只记日志，stop 置位后尽快退出。"""
    while not stop.is_set():
        try:
            await fn()
        except Exception:
            log.exception("periodic.failed", fn=getattr(fn, "__name__", "fn"))
        try:
            await asyncio.wait_for(stop.wait(), interval_s)
        except TimeoutError:
            pass


def active_shop_ids(engine: Engine) -> list[int]:
    """状态为 active 且未暂停的店铺。"""
    with engine.connect() as conn:
        return [
            s["id"] for s in shop_store.list(conn)
            if s["status"] == ACTIVE and not s["paused_reason"]
        ]


async def for_each_active_shop(
    engine: Engine, fn: Callable[[int], Awaitable[Any]]
) -> None:
    async def guarded(shop_id: int) -> None:
        try:
            await fn(shop_id)
        except Exception as e:
            log.warning("periodic.shop_failed", shop_id=shop_id, error=type(e).__name__)

    await asyncio.gather(*(guarded(i) for i in active_shop_ids(engine)))


async def probe_session(runner: Any, shop_id: int) -> None:
    """会话探测：tabcnt。10008 由 ShopRunner 统一处理成 needs_login。"""
    await runner.run(shop_id, lambda client: client.call(ep.TABCNT), actor=SYSTEM_ACTOR)
