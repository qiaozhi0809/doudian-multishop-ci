"""打单台订单池（只读本地库）：待取号 / 已取号两个阶段，附就绪判断与当前面单。"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Engine

from app.domain.errors import InvalidRequest
from app.domain.labeling_rules import order_blockers
from app.store import order_store, shop_store, waybill_store

STAGE_PENDING = "pending"
STAGE_LABELED = "labeled"
STAGE_STATUSES: dict[str, tuple[str, ...]] = {
    STAGE_PENDING: ("synced", "pending_label"),
    STAGE_LABELED: ("label_obtained", "printed"),
}


class LabelPoolService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list(
        self, shop_ids: Sequence[int] | None, stage: str, page: int, page_size: int
    ) -> tuple[list[dict[str, Any]], int]:
        statuses = STAGE_STATUSES.get(stage)
        if statuses is None:
            raise InvalidRequest(f"不支持的阶段: {stage}")
        with self._engine.connect() as conn:
            rows, total = order_store.pool_orders(conn, shop_ids, statuses, page, page_size)
            items = order_store.items_by_order(conn, [r["id"] for r in rows])
            active = waybill_store.active_by_orders(conn, [r["id"] for r in rows])
            names = {s["id"]: s["name"] for s in shop_store.list(conn)}
        out = []
        for r in rows:
            waybill = active.get(r["id"])
            reason = None
            if stage == STAGE_PENDING:
                reasons = order_blockers(
                    r["platform_status"], r["combine_id"], items[r["id"]],
                    waybill is not None, r["status"])
                reason = "；".join(reasons) or None
            out.append({
                "id": r["id"], "shop_id": r["shop_id"],
                "shop_name": names.get(r["shop_id"], ""), "order_no": r["order_no"],
                "status": r["status"], "platform_status": r["platform_status"],
                "combine_id": r["combine_id"], "exception_reason": r["exception_reason"],
                "amount_cents": r["amount_cents"], "pay_time": r["pay_time"],
                "exp_ship_time": r["exp_ship_time"],
                "items": [
                    {k: i[k] for k in (
                        "sku_order_id", "product_id", "product_name", "sku_spec",
                        "quantity", "price_cents")}
                    for i in items[r["id"]]
                ],
                "blocked_reason": reason,
                "waybill": None if waybill is None else {
                    "id": waybill["id"], "courier_code": waybill["courier_code"],
                    "waybill_no": waybill["waybill_no"], "status": waybill["status"],
                    "seq": waybill["seq"], "obtained_at": waybill["obtained_at"],
                    "template_code": waybill["logistics_template_code"],
                },
            })
        return out, int(total)
