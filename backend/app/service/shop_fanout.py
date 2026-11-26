"""跨店只读请求的扇出与单店失败隔离（backend 5.10 共同约束 2）。"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

import structlog

from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.errors import DoudianError
from app.domain.errors import NotFound
from app.service.egress import EgressConflict, EgressNotReady
from app.service.shop_runner import ShopPaused, ShopRunner

log = structlog.get_logger()

Job = Callable[[int, FxgClient], Awaitable[object]]
# 这些异常的文本是写给用户看的；其他异常视为程序缺陷，只记日志
_USER_FACING = (DoudianError, EgressNotReady, EgressConflict, ShopPaused, NotFound)


def user_error(e: Exception) -> str:
    """给用户看的失败原因：业务异常用原文，其他一律「内部错误」（不外泄程序细节）。"""
    if isinstance(e, _USER_FACING):
        return str(e) or type(e).__name__
    return "内部错误"


@dataclass(frozen=True)
class ShopResult[T]:
    shop_id: int
    ok: bool
    data: T | None = None
    error: str | None = None


async def fan_out(
    shop_ids: Sequence[int], runner: ShopRunner, actor: str, job: Job, *, event: str,
) -> list[ShopResult]:
    """每店一条结果；单店失败只影响自己那一条（会话 / 风控仍走 ShopRunner 的统一处理）。"""
    return list(await asyncio.gather(*(_one(i, runner, actor, job, event) for i in shop_ids)))


async def _one(
    shop_id: int, runner: ShopRunner, actor: str, job: Job, event: str,
) -> ShopResult:
    async def wrapped(client: FxgClient) -> object:
        return await job(shop_id, client)

    try:
        return ShopResult(shop_id, True, await runner.run(shop_id, wrapped, actor=actor))
    except _USER_FACING as e:
        return ShopResult(shop_id, False, error=str(e) or type(e).__name__)
    except Exception as e:
        log.error(event, shop_id=shop_id, error=type(e).__name__)
        return ShopResult(shop_id, False, error="内部错误")
