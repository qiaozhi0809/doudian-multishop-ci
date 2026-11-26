"""资金看板（只读）：待结算 / 账单 / 保证金（附录 F）。

账单只查上游不落库（新店为空、金额字段待校准）；待结算是快照，每店整体替换；
保证金按店唯一。所有金额单位一律分。
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.fund_parsers import (
    parse_bills,
    parse_margin,
    parse_unsettled,
    unsettled_display,
)
from app.service.shop_fanout import fan_out
from app.service.shop_runner import ShopRunner
from app.shared.time_bj import BEIJING
from app.store import fund_store, shop_profile_store, shop_store
from app.store.sorting import SortOrder

MAX_PAGES = 20
DEFAULT_BILL_DAYS = 30
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
_BJ_FMT = "%Y-%m-%d %H:%M:%S"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class _SyncData:
    unsettled_count: int
    margin_synced: bool
    note: str | None = None


@dataclass(frozen=True)
class ShopFundSync:
    shop_id: int
    unsettled_count: int
    margin_synced: bool
    note: str | None = None
    error: str | None = None
    synced_at: str | None = None


@dataclass(frozen=True)
class ShopBills:
    shop_id: int
    source: str
    total: int = 0
    items: list[dict[str, Any]] | None = None
    error: str | None = None
    fetched_at: str | None = None


class FundService:
    def __init__(
        self, engine: Engine, runner: ShopRunner,
        clock: Callable[[], datetime] = _utc_now, max_pages: int = MAX_PAGES,
    ) -> None:
        self._engine = engine
        self._runner = runner
        self._clock = clock
        self._max_pages = max_pages

    # ---- 同步（待结算 + 保证金）----

    async def sync(self, shop_ids: Sequence[int], actor: str) -> list[ShopFundSync]:
        results = await fan_out(
            shop_ids, self._runner, actor, self._sync_shop, event="fund.sync.unexpected"
        )
        now = self._stamp()
        return [
            ShopFundSync(
                shop_id=r.shop_id,
                unsettled_count=r.data.unsettled_count if r.data else 0,
                margin_synced=r.data.margin_synced if r.data else False,
                note=r.data.note if r.data else None,
                error=r.error, synced_at=None if r.error else now,
            )
            for r in results
        ]

    async def _sync_shop(self, shop_id: int, client: FxgClient) -> _SyncData:
        now = self._stamp()
        items, complete = await self._fetch_unsettled(client)
        if not complete:
            # 待结算是快照（每店整体替换）：分页没拉全时不能覆盖旧数据
            return _SyncData(0, False, note="待结算分页未拉全，本次未覆盖旧数据")
        with self._engine.begin() as conn:
            fund_store.replace_unsettled(conn, shop_id, items, now)
        with self._engine.connect() as conn:
            shop = shop_store.get(conn, shop_id)
            profile = shop_profile_store.get(conn, shop_id)
        # bizId 即平台店铺ID（api/fund.md F.1c）：优先用店铺ID，为空再回退旧字段 shop_no；
        # 都没有就不发请求
        biz_id = (profile or {}).get("platform_shop_id") or (shop or {}).get("shop_no")
        if not biz_id:
            return _SyncData(len(items), False, note="缺少店铺ID，未同步保证金")
        resp = await client.call(ep.MARGIN_PAYABLE, params=ep.margin_params(str(biz_id)))
        margin = parse_margin(resp)
        with self._engine.begin() as conn:
            fund_store.upsert_margin(conn, shop_id, margin, now)
        return _SyncData(len(items), True)

    async def _fetch_unsettled(self, client: FxgClient) -> tuple[list, bool]:
        collected = []
        base = ep.FUND_QUERY_ITEM.page_base or 0  # 资金 0-based
        for page in range(base, base + self._max_pages):
            resp = await client.call(
                ep.FUND_QUERY_ITEM, body=ep.fund_unsettled_body(page, ep.FUND_PAGE_SIZE)
            )
            items, _total, _cents = parse_unsettled(resp)
            collected.extend(items)
            if len(items) < ep.FUND_PAGE_SIZE:
                return collected, True
        return collected, False

    # ---- 本地概览 ----

    def summary(self, shop_ids: Sequence[int]) -> dict[str, Any]:
        with self._engine.connect() as conn:
            totals = fund_store.unsettled_totals_by_shop(conn, shop_ids)
            margins = {m["shop_id"]: m for m in fund_store.list_margin(conn, shop_ids)}
            synced = fund_store.latest_synced_at(conn, shop_ids)
            names = {s["id"]: s["name"] for s in shop_store.list(conn)}
        shops = []
        for shop_id in shop_ids:
            amount, count = totals.get(shop_id, (0, 0))
            margin = margins.get(shop_id)
            shops.append({
                "shop_id": shop_id, "shop_name": names.get(shop_id, ""),
                "unsettled_amount_cents": amount, "unsettled_count": count,
                "margin_payable_cents": margin["payable_cents"] if margin else None,
                "margin_balance_cents": margin["balance_cents"] if margin else None,
                "margin_level": margin["level"] if margin else None,
                "margin_synced_at": margin["synced_at"] if margin else None,
                "synced_at": synced.get(shop_id),
            })
        return {
            "shops": shops,
            "total_unsettled_amount_cents": sum(s["unsettled_amount_cents"] for s in shops),
            "total_unsettled_count": sum(s["unsettled_count"] for s in shops),
        }

    def list_unsettled(
        self, shop_ids: Sequence[int], page: int = 1, page_size: int = 50,
        sort: str | None = None, order: SortOrder = "asc",
    ) -> tuple[list[dict[str, Any]], int]:
        with self._engine.connect() as conn:
            rows, total = fund_store.list_unsettled(
                conn, shop_ids, page, page_size, sort, order)
            names = {s["id"]: s["name"] for s in shop_store.list(conn)}
        out = []
        for row in rows:
            raw = _raw(row.pop("raw_json"))
            out.append({
                **row, "shop_name": names.get(row["shop_id"], ""),
                "display": unsettled_display(raw),
            })
        return out, total

    def list_margin(self, shop_ids: Sequence[int]) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            rows = fund_store.list_margin(conn, shop_ids)
            names = {s["id"]: s["name"] for s in shop_store.list(conn)}
        return [
            {**{k: v for k, v in r.items() if k != "raw_json"},
             "shop_name": names.get(r["shop_id"], "")}
            for r in rows
        ]

    # ---- 账单（上游，近 N 天）----

    async def bills(
        self, shop_ids: Sequence[int], actor: str, days: int = DEFAULT_BILL_DAYS, page: int = 0,
    ) -> list[ShopBills]:
        start, end = self._bill_range(days)

        async def job(_shop_id: int, client: FxgClient) -> tuple[list[dict[str, Any]], int]:
            resp = await client.call(
                ep.FUND_QUERY_ITEM, body=ep.fund_bills_body(start, end, page)
            )
            items, total = parse_bills(resp)
            return [self._bill_row(i) for i in items], total

        results = await fan_out(
            shop_ids, self._runner, actor, job, event="fund.bills.unexpected"
        )
        fetched = self._stamp()
        return [
            ShopBills(
                shop_id=r.shop_id, source="upstream" if r.ok else "error",
                total=r.data[1] if r.data else 0, items=r.data[0] if r.data else None,
                error=r.error, fetched_at=fetched if r.ok else None,
            )
            for r in results
        ]

    def _bill_range(self, days: int) -> tuple[str, str]:
        end = self._clock().astimezone(BEIJING)
        start = end - timedelta(days=days)
        return start.strftime(_BJ_FMT), end.strftime(_BJ_FMT)

    @staticmethod
    def _bill_row(item) -> dict[str, Any]:
        return {
            "amount_cents": item.amount_cents, "amount_status": item.amount_status,
            "amount_field": item.amount_field, "raw": item.raw,
        }

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
