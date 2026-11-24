"""订单读取：本地库列表（含商品行与店铺名）与各店 tab 计数（经 ShopRunner 请求抖店）。"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.errors import DoudianError
from app.adapter.doudian.parsers import parse_tabcnt
from app.domain.errors import NotFound
from app.domain.order_status import LocalOrderStatus
from app.service.egress import EgressConflict, EgressNotReady
from app.service.shop_runner import ShopPaused, ShopRunner
from app.store import order_store, shop_store

log = structlog.get_logger()

COUNT_KEYS = ("stock_up", "exp_ship", "ship_delay", "in_aftersale")
# 这些异常的文本是写给用户看的；其他异常视为程序缺陷，只记日志
_USER_FACING = (DoudianError, EgressNotReady, EgressConflict, ShopPaused, NotFound)


@dataclass(frozen=True)
class ShopCounts:
    shop_id: int
    source: str  # "upstream" | "error"
    counts: dict[str, int] | None = None
    error: str | None = None


class OrderQueryService:
    def __init__(self, engine: Engine, runner: ShopRunner) -> None:
        self._engine = engine
        self._runner = runner

    def list_orders(
        self, shop_ids: Sequence[int], status: LocalOrderStatus | None, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        with self._engine.connect() as conn:
            rows, total = order_store.list_orders(conn, shop_ids, status, page, page_size)
            items = order_store.items_by_order(conn, [r["id"] for r in rows])
            names = {s["id"]: s["name"] for s in shop_store.list(conn)}
        return [
            {
                "id": r["id"], "shop_id": r["shop_id"], "shop_name": names.get(r["shop_id"], ""),
                "order_no": r["order_no"], "platform_status": r["platform_status"],
                "status": r["status"], "exception_reason": r["exception_reason"],
                "amount_cents": r["amount_cents"], "pay_time": r["pay_time"],
                "exp_ship_time": r["exp_ship_time"],
                "items": [
                    {k: i[k] for k in (
                        "sku_order_id", "product_id", "product_name", "sku_spec",
                        "quantity", "price_cents")}
                    for i in items[r["id"]]
                ],
            }
            for r in rows
        ], total

    async def counts(self, shop_ids: Sequence[int], actor: str) -> list[ShopCounts]:
        """每店一条结果；单店失败只影响自己那一条。"""
        return list(await asyncio.gather(*(self._one(i, actor) for i in shop_ids)))

    async def _one(self, shop_id: int, actor: str) -> ShopCounts:
        async def job(client):
            return parse_tabcnt(await client.call(ep.TABCNT))

        try:
            raw = await self._runner.run(shop_id, job, actor=actor)
        except _USER_FACING as e:
            return ShopCounts(shop_id, "error", error=str(e) or type(e).__name__)
        except Exception as e:
            log.error("order_counts.unexpected", shop_id=shop_id, error=type(e).__name__)
            return ShopCounts(shop_id, "error", error="内部错误")
        return ShopCounts(shop_id, "upstream", counts={k: raw.get(k, 0) for k in COUNT_KEYS})
