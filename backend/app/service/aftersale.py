"""售后聚合（只读）：上游同步、本地列表 / 待办队列、状态计数、详情（附录 E）。"""

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.aftersale_parsers import (
    aftersale_display,
    parse_aftersale_counts,
    parse_aftersale_detail,
    parse_aftersale_list,
)
from app.adapter.doudian.client import FxgClient
from app.domain.aftersale_status import (
    PENDING_FIELDS,
    counts_fields_param,
    is_open,
    pending_total,
)
from app.service.events import AFTERSALES_NEW, EventBus, publish_sync_result
from app.service.periodic import SYSTEM_ACTOR
from app.service.shop_cache import ShopTtlCache
from app.service.shop_fanout import fan_out
from app.service.shop_runner import ShopRunner
from app.store import aftersale_store, shop_store, sync_baseline_store
from app.store.sorting import SortOrder

log = structlog.get_logger()

MAX_PAGES = 50
BASELINE_KIND = "aftersales"
FORCE_SYNC_EVERY = 6  # 计数一直没变时，每店至少每 6 轮（约 30 分钟）完整同步一次
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ShopSync:
    shop_id: int
    fetched: int
    complete: bool
    error: str | None = None
    synced_at: str | None = None
    new: int = 0  # 本次新出现、且仍属待办的售后单（无基线时为 0）
    exhausted: bool = False  # 拉满 MAX_PAGES 页仍未到底（未出错，但不算完整）


@dataclass(frozen=True)
class ShopCounts:
    shop_id: int
    source: str  # "upstream" | "error"
    counts: dict[str, int] | None = None
    pending_total: int = 0
    error: str | None = None
    fetched_at: str | None = None


class AftersaleService:
    def __init__(
        self, engine: Engine, runner: ShopRunner,
        clock: Callable[[], datetime] = _utc_now, events: EventBus | None = None,
    ) -> None:
        self._engine = engine
        self._runner = runner
        self._clock = clock
        self._events = events
        self._counts_cache: ShopTtlCache[dict[str, int]] = ShopTtlCache(clock)
        # 上次跑完（拉全或拉满页数）同步时的各待办分组计数（进程内）；新进程第一轮必然同步一次
        self._last_pending: dict[int, dict[str, int]] = {}
        # 上次同步出错时的计数：同样计数不立即重试，按兜底轮数再试；成功后清掉
        self._failed_pending: dict[int, dict[str, int]] = {}
        self._unchanged: dict[int, int] = {}  # 自上次同步以来计数未变的轮数

    # ---- 同步 ----

    async def sync(self, shop_ids: Sequence[int], actor: str) -> list[ShopSync]:
        """手动同步：每店结束发 SYNC_RESULT（定时检查走 _sync_all，不发「完成」）。"""
        results = await self._sync_all(shop_ids, actor)
        for r in results:
            publish_sync_result(self._events, "aftersales", r.shop_id, r.error)
        return results

    async def _sync_all(self, shop_ids: Sequence[int], actor: str) -> list[ShopSync]:
        results = await fan_out(
            shop_ids, self._runner, actor, self._sync_shop, event="aftersale.sync.unexpected"
        )
        for r in results:  # 同步过的店，下次取计数重新请求平台
            self._counts_cache.invalidate(r.shop_id)
        now = self._stamp()
        return [
            ShopSync(
                shop_id=r.shop_id,
                fetched=int(r.data[0]) if r.data else 0,
                complete=bool(r.data[1]) if r.data else False,
                new=int(r.data[2]) if r.data else 0,
                exhausted=bool(r.data[3]) if r.data else False,
                error=r.error,
                synced_at=None if r.error else now,
            )
            for r in results
        ]

    async def check_new(self, shop_id: int, actor: str = SYSTEM_ACTOR) -> int:
        """定时检查：只取一次计数（60 秒缓存）；各待办分组计数变了才完整同步，
        计数一直不变时每 FORCE_SYNC_EVERY 轮兜底同步一次。返回本次报出的待办新单数。"""
        (c,) = await self.counts([shop_id], actor)
        if c.source != "upstream":
            return 0
        snapshot = {f: int((c.counts or {}).get(f, 0)) for f in PENDING_FIELDS}
        basis = self._failed_pending.get(shop_id, self._last_pending.get(shop_id))
        if basis == snapshot:
            unchanged = self._unchanged.get(shop_id, 0) + 1
            if unchanged < FORCE_SYNC_EVERY:
                self._unchanged[shop_id] = unchanged
                return 0
        (result,) = await self._sync_all([shop_id], actor)
        # 每次同步都算一轮重新计数：拉满页数不会每轮重拉；出错也按兜底轮数再试
        self._unchanged[shop_id] = 0
        if result.error is None:
            self._last_pending[shop_id] = snapshot
            self._failed_pending.pop(shop_id, None)
        else:  # 保留上次成功的快照
            self._failed_pending[shop_id] = snapshot
        return result.new

    async def _sync_shop(
        self, shop_id: int, client: FxgClient,
    ) -> tuple[int, bool, int, bool]:
        now = self._stamp()
        fetched, complete, new, exhausted = 0, False, 0, False
        base = ep.AFTERSALE_LIST.page_base or 1  # 售后列表 1-based
        try:
            for page in range(base, base + MAX_PAGES):
                resp = await client.call(ep.AFTERSALE_LIST, body=ep.aftersale_list_body(page))
                items, _total = parse_aftersale_list(resp)
                with self._engine.begin() as conn:  # 每页立即入库：后面的页失败也不丢
                    known = aftersale_store.existing_ids(
                        conn, shop_id, [a.after_sale_id for a in items])
                    new += len({a.after_sale_id for a in items
                                if a.after_sale_id not in known and is_open(a.status_deadline)})
                    aftersale_store.upsert_aftersales(conn, shop_id, items, now)
                fetched += len(items)
                if len(items) < ep.AFTERSALE_PAGE_SIZE:
                    complete = True
                    break
            else:
                exhausted = True
                log.warning("aftersale.max_pages_exhausted", shop_id=shop_id, pages=MAX_PAGES)
        except BaseException:  # 中途失败也报已入库的新单（下一轮它们已在库里）
            try:
                self._report_new(shop_id, new, now, establish=False)
            except Exception:  # 报告出错不能盖住原异常
                log.exception("aftersale.report_new_failed", shop_id=shop_id)
            raise
        # 先报新单再清理：清理出错也不丢提醒
        # 拉满页数也建基线：最新的售后在前几页，之后新增的都能识别
        reported = self._report_new(shop_id, new, now, establish=complete or exhausted)
        if complete:  # 只有拉全了才能判断哪些售后单已不在平台列表
            with self._engine.begin() as conn:
                aftersale_store.prune_unseen(conn, shop_id, now)
        return fetched, complete, reported, exhausted

    def _report_new(self, shop_id: int, new: int, now: str, *, establish: bool) -> int:
        """有基线：报本轮新入库的待办单（部分同步也报）。无基线：不报，返回 0；
        拉全或拉满页数（未出错）才建基线（0 条也建）。"""
        with self._engine.begin() as conn:
            if not sync_baseline_store.has(conn, shop_id, BASELINE_KIND):
                if establish:
                    sync_baseline_store.establish(conn, shop_id, BASELINE_KIND, now)
                return 0
        if new > 0 and self._events is not None:
            self._events.publish(AFTERSALES_NEW, {"shop_id": shop_id, "count": new})
        return new

    # ---- 本地列表 / 待办 ----

    def list_local(
        self, shop_ids: Sequence[int], *, status: int | None = None, open_only: bool = False,
        keyword: str | None = None, by_deadline: bool = False, page: int = 1,
        page_size: int = 50, sort: str | None = None, order: SortOrder = "asc",
        quick: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        due_before = (self._clock() + timedelta(hours=24)).strftime(_ISO_FMT)
        with self._engine.connect() as conn:
            rows, total = aftersale_store.list_aftersales(
                conn, shop_ids, status=status, open_only=open_only, keyword=keyword,
                by_deadline=by_deadline, page=page, page_size=page_size,
                sort=sort, order=order, quick=quick, due_before=due_before,
            )
            names = {s["id"]: s["name"] for s in shop_store.list(conn)}
        return [self._row(r, names) for r in rows], total

    @staticmethod
    def _row(row: Mapping[str, Any], names: Mapping[int, str]) -> dict[str, Any]:
        base = aftersale_store.display_row(row)
        display = aftersale_display(base.pop("detail"))
        return {
            **base, "shop_name": names.get(row["shop_id"], ""),
            "display": display,
        }

    def statuses(self, shop_ids: Sequence[int]) -> list[dict[str, Any]]:
        """本地出现过的状态 + 平台文案（数字枚举取值未公开，不自己造标签）。"""
        with self._engine.connect() as conn:
            rows = aftersale_store.list_statuses(conn, shop_ids)
        out = []
        for status, detail_json in rows:
            raw: dict = {}
            if detail_json:
                try:
                    parsed = json.loads(detail_json)
                    raw = parsed if isinstance(parsed, dict) else {}
                except ValueError:
                    raw = {}
            label = aftersale_display(raw).get("status_text") or f"状态 {status}"
            out.append({"status": status, "label": label})
        return out

    # ---- 状态计数（上游，单店失败隔离）----

    async def counts(self, shop_ids: Sequence[int], actor: str) -> list[ShopCounts]:
        """每店缓存 60 秒（shop_cache）；fetched_at 是数据当初取自平台的时间。"""
        results = await self._counts_cache.fan_out(
            shop_ids, self._runner, actor, self._counts_job,
            event="aftersale.counts.unexpected",
        )
        return [
            ShopCounts(
                shop_id=r.shop_id, source="upstream" if r.ok else "error",
                counts=dict(r.data) if r.data else r.data,
                pending_total=pending_total(r.data or {}),
                error=r.error, fetched_at=at.strftime(_ISO_FMT) if at else None,
            )
            for r, at in results
        ]

    @staticmethod
    async def _counts_job(_shop_id: int, client: FxgClient) -> dict[str, int]:
        resp = await client.call(
            ep.AFTERSALE_COUNTS, params=ep.aftersale_counts_params(counts_fields_param())
        )
        return parse_aftersale_counts(resp)

    # ---- 详情（上游，按需）----

    async def detail(self, shop_id: int, after_sale_id: str, actor: str) -> dict:
        async def job(client: FxgClient) -> dict:
            resp = await client.call(
                ep.AFTERSALE_DETAIL, params=ep.aftersale_detail_params(after_sale_id)
            )
            return parse_aftersale_detail(resp)

        return await self._runner.run(shop_id, job, actor=actor)

    def _stamp(self) -> str:
        return self._clock().strftime(_ISO_FMT)
