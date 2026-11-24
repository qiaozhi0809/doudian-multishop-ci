"""店铺任务统一入口：所有会请求抖店的操作都经 ShopRunner.run（backend 5.17）。

顺序：店铺未暂停 → 出口检查 → 进该店串行队列 → 组装客户端（该店出口 + 审计）→ 执行。
任何一步不通都不会发出请求，更不会退回直连。
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Protocol, TypeVar

from sqlalchemy import Engine

from app.adapter.doudian.client import FxgClient, ShopCredentials
from app.adapter.doudian.errors import EgressUnavailable, RiskBlocked, SessionExpired
from app.adapter.doudian.pacer import ShopPacer
from app.adapter.doudian.transport import CurlTransport
from app.domain.audit import CallRecord
from app.domain.errors import NotFound
from app.service.events import SHOP_STATUS_CHANGED, EventBus
from app.service.scheduler import ShopScheduler
from app.service.session_manager import SessionManager
from app.store import audit_store, shop_store

T = TypeVar("T")

_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
RISK_PAUSE_PREFIX = "risk_blocked:"

Observer = Callable[[CallRecord], None]
ClientFactory = Callable[[ShopCredentials, str | None, str, Observer], FxgClient]


class ShopPaused(Exception):
    """店铺处于风控暂停，等待人工恢复。"""

    def __init__(self, shop_id: int, reason: str) -> None:
        super().__init__(f"店铺已暂停（{reason}），请人工检查后恢复")
        self.shop_id = shop_id
        self.reason = reason


class EgressGate(Protocol):
    async def ensure_ready(self, shop_id: int) -> None: ...

    def proxy_for(self, shop_id: int) -> str | None: ...

    def mark_unreachable(self, shop_id: int) -> None: ...


def default_client_factory(
    creds: ShopCredentials, proxy: str | None, actor: str, observer: Callable[[CallRecord], None]
) -> FxgClient:
    return FxgClient(CurlTransport(proxy), creds, ShopPacer(), observer, actor)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ShopRunner:
    def __init__(
        self, engine: Engine, scheduler: ShopScheduler, egress: EgressGate,
        sessions: SessionManager, client_factory: ClientFactory = default_client_factory,
        events: EventBus | None = None, clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._engine = engine
        self._scheduler = scheduler
        self._egress = egress
        self._sessions = sessions
        self._factory = client_factory
        self._events = events or sessions.events
        self._clock = clock

    async def run(
        self, shop_id: int, job: Callable[[FxgClient], Awaitable[T]], *, actor: str,
        needs_session: bool = True,
    ) -> T:
        """needs_session=False 用于扫码登录：此时 job 拿到的客户端不带任何凭证，不得用来发请求。"""
        self._ensure_not_paused(shop_id)
        await self._egress.ensure_ready(shop_id)

        async def in_queue() -> T:
            # 排队期间前一个任务可能触发了风控暂停：执行前再查一次
            self._ensure_not_paused(shop_id)
            if needs_session:
                creds = self._sessions.get_credentials(shop_id)
            else:
                creds = ShopCredentials(shop_id, [], "", {})
            client = self._factory(creds, self._egress.proxy_for(shop_id), actor, self._audit)
            try:
                return await job(client)
            except RiskBlocked as e:
                self._pause(shop_id, f"{RISK_PAUSE_PREFIX}{e.code}")
                raise
            except SessionExpired:
                self._sessions.mark_expired(shop_id)
                raise
            except EgressUnavailable:
                self._egress.mark_unreachable(shop_id)  # 作废「出口 ok」缓存，下次必须重查
                raise

        return await self._scheduler.run(shop_id, in_queue)

    def _ensure_not_paused(self, shop_id: int) -> None:
        with self._engine.connect() as conn:
            shop = shop_store.get(conn, shop_id)
        if shop is None:
            raise NotFound(f"店铺不存在: {shop_id}", shop_id)
        if shop["paused_reason"]:
            raise ShopPaused(shop_id, shop["paused_reason"])

    def _audit(self, record: CallRecord) -> None:
        with self._engine.begin() as conn:
            audit_store.insert(conn, record, self._clock().strftime(_ISO_FMT))

    def _pause(self, shop_id: int, reason: str) -> None:
        with self._engine.begin() as conn:
            shop_store.set_paused(conn, shop_id, reason, self._clock().strftime(_ISO_FMT))
            status = shop_store.get(conn, shop_id)["status"]
        self._events.publish(SHOP_STATUS_CHANGED, {
            "shop_id": shop_id, "status": status, "paused_reason": reason,
        })
