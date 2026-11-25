"""售后聚合（只读）：上游同步、本地列表 / 待办队列、状态计数、详情（附录 E）。"""

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.aftersale_parsers import (
    aftersale_display,
    parse_aftersale_counts,
    parse_aftersale_detail,
    parse_aftersale_list,
)
from app.adapter.doudian.client import FxgClient
from app.domain.aftersale_status import counts_fields_param, pending_total
from app.service.shop_fanout import fan_out
from app.service.shop_runner import ShopRunner
from app.store import aftersale_store, shop_store

MAX_PAGES = 50
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
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._engine = engine
        self._runner = runner
        self._clock = clock

    # ---- 同步 ----

    async def sync(self, shop_ids: Sequence[int], actor: str) -> list[ShopSync]:
        results = await fan_out(
            shop_ids, self._runner, actor, self._sync_shop, event="aftersale.sync.unexpected"
        )
        now = self._stamp()
        return [
            ShopSync(
                shop_id=r.shop_id,
                fetched=int(r.data[0]) if r.data else 0,
                complete=bool(r.data[1]) if r.data else False,
                error=r.error,
                synced_at=None if r.error else now,
            )
            for r in results
        ]

    async def _sync_shop(self, shop_id: int, client: FxgClient) -> tuple[int, bool]:
        now = self._stamp()
        fetched, complete = 0, False
        base = ep.AFTERSALE_LIST.page_base or 1  # 售后列表 1-based
        for page in range(base, base + MAX_PAGES):
            resp = await client.call(ep.AFTERSALE_LIST, body=ep.aftersale_list_body(page))
            items, _total = parse_aftersale_list(resp)
            with self._engine.begin() as conn:  # 每页立即入库：后面的页失败也不丢
                aftersale_store.upsert_aftersales(conn, shop_id, items, now)
            fetched += len(items)
            if len(items) < ep.AFTERSALE_PAGE_SIZE:
                complete = True
                break
        if complete:  # 只有拉全了才能判断哪些售后单已不在平台列表
            with self._engine.begin() as conn:
                aftersale_store.prune_unseen(conn, shop_id, now)
        return fetched, complete

    # ---- 本地列表 / 待办 ----

    def list_local(
        self, shop_ids: Sequence[int], *, status: int | None = None, open_only: bool = False,
        keyword: str | None = None, by_deadline: bool = False, page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        with self._engine.connect() as conn:
            rows, total = aftersale_store.list_aftersales(
                conn, shop_ids, status=status, open_only=open_only, keyword=keyword,
                by_deadline=by_deadline, page=page, page_size=page_size,
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
        results = await fan_out(
            shop_ids, self._runner, actor, self._counts_job,
            event="aftersale.counts.unexpected",
        )
        fetched = self._stamp()
        return [
            ShopCounts(
                shop_id=r.shop_id, source="upstream" if r.ok else "error",
                counts=r.data, pending_total=pending_total(r.data or {}),
                error=r.error, fetched_at=fetched if r.ok else None,
            )
            for r in results
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
