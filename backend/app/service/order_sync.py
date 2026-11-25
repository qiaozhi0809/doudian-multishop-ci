"""待发货订单同步（backend 5.4、flows 7.2）：分页拉取、每页立即入库、离队订单补查。"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.parsers import parse_orders
from app.domain.order_status import LocalOrderStatus, PlatformOrderStatus
from app.service.events import SYNC_PROGRESS, EventBus
from app.service.session_manager import SessionManager
from app.service.shop_runner import ShopRunner
from app.store import order_store

log = structlog.get_logger()

MAX_PAGES = 100
MAX_RECHECK_PER_RUN = 50  # 补查是一单一请求：每轮设上限，其余留到下一轮
NOT_FOUND_REASON = "平台查不到该订单"
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class SyncResult:
    fetched: int
    upserted: int
    cancelled: int
    rechecked: int
    complete: bool


def _now() -> str:
    return datetime.now(UTC).strftime(_ISO_FMT)


class OrderSyncService:
    def __init__(
        self, engine: Engine, runner: ShopRunner, sessions: SessionManager, events: EventBus,
        max_pages: int = MAX_PAGES, on_synced: Callable[[int], None] | None = None,
    ) -> None:
        self._engine = engine
        self._runner = runner
        self._sessions = sessions  # 会话失效由 ShopRunner 统一处理，这里不重复判断
        self._events = events
        self._max_pages = max_pages
        self._on_synced = on_synced

    async def sync_pending(self, shop_id: int, actor: str) -> SyncResult:
        async def job(client: FxgClient) -> SyncResult:
            return await self._sync(client, shop_id)

        try:
            return await self._runner.run(shop_id, job, actor=actor)
        finally:
            if self._on_synced:  # 订单已变：该店的 tab 计数缓存作废
                self._on_synced(shop_id)

    async def _sync(self, client: FxgClient, shop_id: int) -> SyncResult:
        fetched, seen, complete = 0, set[str](), False
        for page in range(ep.SEARCHLIST_PAGE_BASE, ep.SEARCHLIST_PAGE_BASE + self._max_pages):
            resp = await client.call(ep.SEARCHLIST, params=ep.searchlist_pending_params(page))
            orders = parse_orders(resp)
            with self._engine.begin() as conn:  # 每页立即入库：后面的页失败也不丢
                order_store.upsert_orders(conn, shop_id, orders, _now())
            fetched += len(orders)
            seen.update(o.order_no for o in orders)
            self._events.publish(
                SYNC_PROGRESS, {"shop_id": shop_id, "kind": "orders", "fetched": fetched}
            )
            if len(orders) < ep.SEARCHLIST_MAX_PAGE_SIZE:
                complete = True
                break
        rechecked, cancelled = 0, 0
        if complete:  # 分页没拉全时，「没出现」不代表离开了待发货
            rechecked, cancelled = await self._recheck_vanished(client, shop_id, seen)
        return SyncResult(fetched, fetched, cancelled, rechecked, complete)

    async def _recheck_vanished(
        self, client: FxgClient, shop_id: int, seen: set[str]
    ) -> tuple[int, int]:
        with self._engine.connect() as conn:
            by_age = order_store.recheck_candidates_by_age(conn, shop_id)
        vanished = [n for n in by_age if n not in seen][:MAX_RECHECK_PER_RUN]
        rechecked, cancelled = 0, 0
        for order_no in vanished:
            resp = await client.call(
                ep.SEARCHLIST, params=ep.searchlist_by_order_id_params(order_no)
            )
            rechecked += 1
            found = [o for o in parse_orders(resp) if o.order_no == order_no]
            if not found:
                # 平台查不到：标成异常，离开候选集并在界面可见，不再被反复请求
                log.warning("order_sync.recheck_not_found", shop_id=shop_id, order_no=order_no)
                with self._engine.begin() as conn:
                    order_store.mark_exception(conn, shop_id, order_no, NOT_FOUND_REASON, _now())
                continue
            with self._engine.begin() as conn:
                order_store.upsert_orders(conn, shop_id, found, _now())
                # 候选集已排除本地已发货 / 已关闭 / 已取消的单
                if found[0].platform_status == PlatformOrderStatus.CLOSED:
                    order_store.set_local_status(
                        conn, shop_id, order_no, LocalOrderStatus.CANCELLED, _now()
                    )
                    cancelled += 1
        return rechecked, cancelled
