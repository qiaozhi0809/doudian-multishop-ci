"""商品 / 库存聚合（只读）：上游同步、本地列表、计数、分组、仓库与预警（附录 D）。"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.catalog_parsers import (
    parse_product_counts,
    parse_product_groups,
    parse_products,
    parse_stock,
    parse_warehouses,
    product_display,
)
from app.adapter.doudian.client import FxgClient
from app.service.shop_cache import ShopTtlCache
from app.service.shop_fanout import ShopResult, fan_out
from app.service.shop_runner import ShopRunner
from app.store import catalog_store, shop_store
from app.store.sorting import SortOrder

MAX_PAGES = 50
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ShopProductSync:
    shop_id: int
    fetched: int
    complete: bool
    error: str | None = None
    synced_at: str | None = None


@dataclass(frozen=True)
class ShopStockSync:
    shop_id: int
    fetched: int
    complete: bool
    alarm_count: int = 0
    sold_out_count: int = 0
    error: str | None = None
    synced_at: str | None = None


@dataclass(frozen=True)
class ShopCounts:
    shop_id: int
    source: str
    counts: dict[str, int] | None = None
    error: str | None = None
    fetched_at: str | None = None


@dataclass(frozen=True)
class ShopItems:
    shop_id: int
    source: str
    items: list[dict[str, Any]] | None = None
    error: str | None = None
    fetched_at: str | None = None


class CatalogService:
    def __init__(
        self, engine: Engine, runner: ShopRunner,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._engine = engine
        self._runner = runner
        self._clock = clock
        self._counts_cache: ShopTtlCache[dict[str, int]] = ShopTtlCache(clock)

    # ---- 商品同步 ----

    async def sync_products(self, shop_ids: Sequence[int], actor: str) -> list[ShopProductSync]:
        results = await fan_out(
            shop_ids, self._runner, actor, self._sync_products_shop,
            event="catalog.products.sync.unexpected",
        )
        for r in results:  # 同步过的店，下次取商品计数重新请求平台
            self._counts_cache.invalidate(r.shop_id)
        now = self._stamp()
        return [
            ShopProductSync(
                shop_id=r.shop_id, fetched=int(r.data[0]) if r.data else 0,
                complete=bool(r.data[1]) if r.data else False, error=r.error,
                synced_at=None if r.error else now,
            )
            for r in results
        ]

    async def _sync_products_shop(self, shop_id: int, client: FxgClient) -> tuple[int, bool]:
        now = self._stamp()
        fetched, complete = 0, False
        base = ep.PRODUCT_LIST.page_base or 0  # 商品列表 0-based
        for page in range(base, base + MAX_PAGES):
            resp = await client.call(
                ep.PRODUCT_LIST, params=ep.product_list_params(page, ep.PRODUCT_PAGE_SIZE)
            )
            items, _total = parse_products(resp)
            with self._engine.begin() as conn:
                catalog_store.upsert_products(conn, shop_id, items, now)
            fetched += len(items)
            if len(items) < ep.PRODUCT_PAGE_SIZE:
                complete = True
                break
        if complete:
            with self._engine.begin() as conn:
                catalog_store.prune_products(conn, shop_id, now)
        return fetched, complete

    def list_products(
        self, shop_ids: Sequence[int], *, tab: str | None = None, keyword: str | None = None,
        page: int = 1, page_size: int = 50, sort: str | None = None, order: SortOrder = "asc",
        quick: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        with self._engine.connect() as conn:
            rows, total = catalog_store.list_products(
                conn, shop_ids, tab=tab, keyword=keyword, page=page, page_size=page_size,
                sort=sort, order=order, quick=quick,
            )
            names = {s["id"]: s["name"] for s in shop_store.list(conn)}
        out = []
        for row in rows:
            display = product_display(_raw(row.pop("raw_json")))
            out.append({**row, "shop_name": names.get(row["shop_id"], ""), "display": display})
        return out, total

    # ---- 商品计数 / 分组（上游，单店失败隔离）----

    async def product_counts(self, shop_ids: Sequence[int], actor: str) -> list[ShopCounts]:
        """每店缓存 60 秒（shop_cache）；fetched_at 是数据当初取自平台的时间。"""
        results = await self._counts_cache.fan_out(
            shop_ids, self._runner, actor, self._counts_job,
            event="catalog.products.counts.unexpected",
        )
        return [
            ShopCounts(
                shop_id=r.shop_id, source="upstream" if r.ok else "error",
                counts=dict(r.data) if r.data else r.data,
                error=r.error, fetched_at=at.strftime(_ISO_FMT) if at else None,
            )
            for r, at in results
        ]

    @staticmethod
    async def _counts_job(_shop_id: int, client: FxgClient) -> dict[str, int]:
        return parse_product_counts(await client.call(ep.PRODUCT_COUNTS))

    async def product_groups(self, shop_ids: Sequence[int], actor: str) -> list[ShopItems]:
        async def job(_shop_id: int, client: FxgClient) -> list[dict[str, Any]]:
            groups = parse_product_groups(await client.call(ep.PRODUCT_GROUPS))
            return [{"group_id": g.group_id, "name": g.name} for g in groups]

        results = await fan_out(
            shop_ids, self._runner, actor, job, event="catalog.products.groups.unexpected"
        )
        return self._items(results)

    # ---- 库存同步 ----

    async def sync_stock(self, shop_ids: Sequence[int], actor: str) -> list[ShopStockSync]:
        results = await fan_out(
            shop_ids, self._runner, actor, self._sync_stock_shop,
            event="catalog.stock.sync.unexpected",
        )
        now = self._stamp()
        return [
            ShopStockSync(
                shop_id=r.shop_id, fetched=int(r.data[0]) if r.data else 0,
                complete=bool(r.data[1]) if r.data else False,
                alarm_count=int(r.data[2]) if r.data else 0,
                sold_out_count=int(r.data[3]) if r.data else 0,
                error=r.error, synced_at=None if r.error else now,
            )
            for r in results
        ]

    async def _sync_stock_shop(self, shop_id: int, client: FxgClient) -> tuple[int, bool, int, int]:
        now = self._stamp()
        fetched, complete = 0, False
        alarm, sold_out = 0, 0
        base = ep.STOCK_LIST.page_base or 1  # 库存列表 1-based
        for page in range(base, base + MAX_PAGES):
            resp = await client.call(
                ep.STOCK_LIST, body=ep.stock_list_body(page, ep.STOCK_PAGE_SIZE)
            )
            items, summary = parse_stock(resp)
            with self._engine.begin() as conn:
                catalog_store.upsert_stock(conn, shop_id, items, now)
            fetched += len(items)
            alarm, sold_out = summary.stock_alarm_cnt, summary.sold_out_cnt
            if len(items) < ep.STOCK_PAGE_SIZE:
                complete = True
                break
        if complete:
            with self._engine.begin() as conn:
                catalog_store.prune_stock(conn, shop_id, now)
        return fetched, complete, alarm, sold_out

    # ---- 库存读取 ----

    def list_stock(
        self, shop_ids: Sequence[int], *, alarm_only: bool = False, page: int = 1,
        page_size: int = 50, sort: str | None = None, order: SortOrder = "asc",
        quick: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        with self._engine.connect() as conn:
            rows, total = catalog_store.list_stock(
                conn, shop_ids, alarm_only=alarm_only, page=page, page_size=page_size,
                sort=sort, order=order, quick=quick,
            )
            names = {s["id"]: s["name"] for s in shop_store.list(conn)}
        return [{**r, "shop_name": names.get(r["shop_id"], "")} for r in rows], total

    def stock_summary(self, shop_ids: Sequence[int]) -> dict[str, int]:
        with self._engine.connect() as conn:
            return catalog_store.stock_summary(conn, shop_ids)

    async def warehouses(self, shop_ids: Sequence[int], actor: str) -> list[ShopItems]:
        async def job(_shop_id: int, client: FxgClient) -> list[dict[str, Any]]:
            warehouses = parse_warehouses(await client.call(ep.STOCK_WAREHOUSES))
            return [{"warehouse_id": w.warehouse_id, "name": w.name} for w in warehouses]

        results = await fan_out(
            shop_ids, self._runner, actor, job, event="catalog.stock.warehouses.unexpected"
        )
        return self._items(results)

    def _items(self, results: Sequence[ShopResult]) -> list[ShopItems]:
        fetched = self._stamp()
        return [
            ShopItems(
                shop_id=r.shop_id, source="upstream" if r.ok else "error", items=r.data,
                error=r.error, fetched_at=fetched if r.ok else None,
            )
            for r in results
        ]

    def _stamp(self) -> str:
        return self._clock().strftime(_ISO_FMT)


def _raw(raw_json: Any) -> dict:
    if not raw_json:
        return {}
    try:
        parsed = json.loads(raw_json)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
