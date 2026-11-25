"""按需解密收件人（DEC-06、flows 7.3）。

约束：
- 只对「待发货 / 待打单」链路解密；已发货 / 已完成 / 已取消不解密。
- 明文只在内存缓存到平台返回的 `expire_time`，不落库、不写日志。
- 单店连续解密间隔 ≥ 2 秒；捕获 602502151 后该店解密冷却 3 小时，
  只暂停解密、不暂停取号（取号不依赖解密）。
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.error_codes import DECRYPT_RATE_RISK
from app.adapter.doudian.errors import BizRejected, RiskBlocked
from app.adapter.doudian.label_parsers import parse_receiver
from app.domain.errors import DecryptCooldown, InvalidRequest, NotFound
from app.domain.labeling_rules import decrypt_allowed
from app.domain.models import ReceiverInfo
from app.service.shop_runner import ShopRunner
from app.store import order_store

MIN_DECRYPT_GAP_S = 2.0  # 0.5~0.8s 会触发风控；2 秒为保守估计（gaps API-10）
DECRYPT_COOLDOWN_S = 3 * 3600  # 602502151 后约 3 小时恢复（flows 7.3）
CACHE_FALLBACK_S = 600  # 平台未给 expire_time 时的保守缓存时长
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
_EXEMPT = frozenset({DECRYPT_RATE_RISK})


@dataclass(frozen=True)
class ReceiverView:
    name: str | None
    phone: str | None
    region: str | None
    detail: str | None
    expire_at: str | None
    cached: bool = False


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _parse_iso(value: str) -> datetime:
    return datetime.strptime(value, _ISO_FMT).replace(tzinfo=UTC)


class ReceiverService:
    def __init__(
        self, engine: Engine, runner: ShopRunner, *, clock: Callable[[], datetime] = _utc_now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._engine = engine
        self._runner = runner
        self._clock = clock
        self._sleep = sleep
        self._cache: dict[tuple[int, str], tuple[ReceiverInfo, datetime]] = {}
        self._last_call: dict[int, datetime] = {}
        self._cooldown: dict[int, datetime] = {}

    async def decrypt(self, order_id: int, actor: str) -> ReceiverView:
        with self._engine.connect() as conn:
            order = next(iter(order_store.get_by_ids(conn, [order_id])), None)
        if order is None:
            raise NotFound(f"订单不存在: {order_id}", None)
        if not decrypt_allowed(order["status"], order["platform_status"]):
            raise InvalidRequest("该订单已发货或已取消，不再解密（避免消耗额度）")

        shop_id, order_no = order["shop_id"], order["order_no"]
        now = self._clock()
        cached = self._cache.get((shop_id, order_no))
        if cached and now < cached[1]:
            return self._view(cached[0], cached=True)

        until = self._cooldown.get(shop_id)
        if until and now < until:
            raise DecryptCooldown(shop_id=shop_id)

        last = self._last_call.get(shop_id)
        if last is not None:
            wait = MIN_DECRYPT_GAP_S - (now - last).total_seconds()
            if wait > 0:
                await self._sleep(wait)
        self._last_call[shop_id] = self._clock()

        async def job(client):
            return parse_receiver(await client.call(ep.RECEIVE_INFO, params={"order_id": order_no}))

        try:
            info = await self._runner.run(
                shop_id, job, actor=actor, risk_pause_exempt=_EXEMPT)
        except RiskBlocked as e:
            if e.code == DECRYPT_RATE_RISK:
                self._cooldown[shop_id] = self._clock() + timedelta(seconds=DECRYPT_COOLDOWN_S)
                raise DecryptCooldown(shop_id=shop_id) from None
            raise
        if info.verify_type:
            raise BizRejected("verify_required", "该店需要完成平台验证后才能解密")

        expire = (_parse_iso(info.expire_at) if info.expire_at
                  else self._clock() + timedelta(seconds=CACHE_FALLBACK_S))
        if expire > self._clock():
            self._cache[(shop_id, order_no)] = (info, expire)
        return self._view(info, cached=False)

    @staticmethod
    def _view(info: ReceiverInfo, *, cached: bool) -> ReceiverView:
        return ReceiverView(info.name, info.phone, info.region, info.detail,
                            info.expire_at, cached=cached)
