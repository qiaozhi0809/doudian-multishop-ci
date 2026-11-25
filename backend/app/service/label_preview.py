"""两步提交第①步：取号 / 一体 / 作废的预览（backend 5.11、flows 7.3）。

只读本地库：不请求抖店、不发写请求。预览 10 分钟有效、一次性、按管理员归属。
执行前订单可能已变化，执行阶段会重新校验（见 labeling）。
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy import Engine

from app.domain.errors import InvalidRequest, NotFound
from app.domain.labeling_rules import (
    VOIDABLE_STATUSES,
    order_blockers,
    pick_courier,
    select_account,
)
from app.domain.order_status import LocalOrderStatus
from app.store import (
    base_data_store,
    order_store,
    shop_store,
    waybill_store,
)

log = structlog.get_logger()

PREVIEW_TTL_S = 600
MODE_OBTAIN = "obtain"
MODE_FETCH_AND_SHIP = "fetch_and_ship"
MODE_VOID = "void"
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class ShopPlan:
    shop_id: int
    shop_name: str
    courier_code: str
    courier_name: str | None
    template_code: str
    ebill_id: str
    net_code: str
    account_balance: int | None
    address: Mapping[str, Any]
    order_ids: tuple[int, ...]


@dataclass(frozen=True)
class VoidPlan:
    shop_id: int
    shop_name: str
    waybill_ids: tuple[int, ...]


@dataclass(frozen=True)
class BlockedOrder:
    shop_id: int
    shop_name: str
    order_id: int
    order_no: str
    reason: str


@dataclass(frozen=True)
class ShopError:
    shop_id: int
    shop_name: str
    reason: str


@dataclass(frozen=True)
class PreviewRecord:
    preview_id: str
    mode: str
    actor: str
    created_at: datetime
    dry_run: bool
    shops: tuple[ShopPlan, ...] = ()
    void_plans: tuple[VoidPlan, ...] = ()
    blocked: tuple[BlockedOrder, ...] = ()
    shop_errors: tuple[ShopError, ...] = ()


class PreviewStore:
    def __init__(self, clock, ttl_s: int = PREVIEW_TTL_S) -> None:
        self._clock = clock
        self._ttl = timedelta(seconds=ttl_s)
        self._items: dict[str, PreviewRecord] = {}

    def put(self, record: PreviewRecord) -> None:
        self._items[record.preview_id] = record

    def take(self, preview_id: str, actor: str) -> PreviewRecord:
        record = self._items.get(preview_id)
        if record is None:
            raise InvalidRequest("预览不存在或已使用，请重新预览")
        if record.actor != actor:
            raise InvalidRequest("预览不属于当前管理员")
        if self._clock() - record.created_at > self._ttl:
            self._items.pop(preview_id, None)
            raise InvalidRequest("预览已失效，请重新预览")
        return self._items.pop(preview_id)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class LabelPreviewService:
    def __init__(
        self, engine: Engine, *, dry_run: bool, clock=_utc_now, ttl_s: int = PREVIEW_TTL_S,
    ) -> None:
        self._engine = engine
        self._dry_run = dry_run
        self._clock = clock
        self.previews = PreviewStore(clock, ttl_s)

    # ---- 预览 ----

    def preview_obtain(
        self, order_ids: Sequence[int], courier_by_shop: Mapping[str | int, str],
        actor: str, mode: str = MODE_OBTAIN,
    ) -> PreviewRecord:
        self._check_mode(mode, (MODE_OBTAIN, MODE_FETCH_AND_SHIP))
        preferred = {int(k): v for k, v in courier_by_shop.items()}
        with self._engine.connect() as conn:
            rows = self._load_orders(conn, order_ids)
            by_shop = self._group(rows)
            shops, blocked, errors = [], [], []
            for shop_id, shop_orders in by_shop.items():
                shop = shop_store.get(conn, shop_id)
                plan, shop_error = self._shop_plan(conn, shop, preferred.get(shop_id))
                if plan is None:
                    errors.append(ShopError(shop_id, shop["name"], shop_error))
                    blocked.extend(
                        BlockedOrder(shop_id, shop["name"], o["id"], o["order_no"], shop_error)
                        for o in shop_orders
                    )
                    continue
                active = waybill_store.active_by_orders(conn, [o["id"] for o in shop_orders])
                items = order_store.items_by_order(conn, [o["id"] for o in shop_orders])
                ready = []
                for o in shop_orders:
                    reasons = order_blockers(
                        o["platform_status"], o["combine_id"], items[o["id"]],
                        o["id"] in active, o["status"],
                    )
                    if reasons:
                        blocked.append(BlockedOrder(
                            shop_id, shop["name"], o["id"], o["order_no"], "；".join(reasons)))
                    else:
                        ready.append(o["id"])
                if ready:
                    shops.append(ShopPlan(
                        shop_id, shop["name"], plan["courier_code"], plan["courier_name"],
                        plan["template_code"], plan["ebill_id"], plan["net_code"],
                        plan["account_balance"], plan["address"], tuple(ready),
                    ))
            record = PreviewRecord(
                uuid4().hex, mode, actor, self._clock(), self._dry_run,
                shops=tuple(shops), blocked=tuple(blocked), shop_errors=tuple(errors),
            )
            self._mark_pending(conn, record)
        self.previews.put(record)
        return record

    def preview_void(self, order_ids: Sequence[int], actor: str) -> PreviewRecord:
        with self._engine.connect() as conn:
            rows = self._load_orders(conn, order_ids)
            by_shop = self._group(rows)
            plans, blocked, errors = [], [], []
            for shop_id, shop_orders in by_shop.items():
                shop = shop_store.get(conn, shop_id)
                if shop["status"] != "active" or shop["paused_reason"]:
                    reason = "店铺未登录或已暂停"
                    errors.append(ShopError(shop_id, shop["name"], reason))
                    blocked.extend(
                        BlockedOrder(shop_id, shop["name"], o["id"], o["order_no"], reason)
                        for o in shop_orders
                    )
                    continue
                active = waybill_store.active_by_orders(conn, [o["id"] for o in shop_orders])
                waybill_ids = []
                for o in shop_orders:
                    reason = self._void_blocker(o, active.get(o["id"]))
                    if reason:
                        blocked.append(BlockedOrder(
                            shop_id, shop["name"], o["id"], o["order_no"], reason))
                    else:
                        waybill_ids.append(active[o["id"]]["id"])
                if waybill_ids:
                    plans.append(VoidPlan(shop_id, shop["name"], tuple(waybill_ids)))
            record = PreviewRecord(
                uuid4().hex, MODE_VOID, actor, self._clock(), self._dry_run,
                void_plans=tuple(plans), blocked=tuple(blocked), shop_errors=tuple(errors),
            )
        self.previews.put(record)
        return record

    # ---- 视图 ----

    def view(self, record: PreviewRecord) -> dict[str, Any]:
        if record.mode == MODE_VOID:
            return self._void_view(record)
        shops = [
            {
                "shop_id": p.shop_id, "shop_name": p.shop_name,
                "courier_code": p.courier_code, "courier_name": p.courier_name,
                "template_code": p.template_code, "ebill_id": p.ebill_id,
                "net_code": p.net_code, "account_balance": p.account_balance,
                "ready_order_ids": list(p.order_ids),
            }
            for p in record.shops
        ]
        return {
            "preview_id": record.preview_id, "mode": record.mode,
            "shops": shops,
            "blocked": [vars(b) for b in record.blocked],
            "shop_errors": [vars(e) for e in record.shop_errors],
            "total_ready": sum(len(p.order_ids) for p in record.shops),
            "total_blocked": len(record.blocked),
            "dry_run": record.dry_run,
        }

    def _void_view(self, record: PreviewRecord) -> dict[str, Any]:
        with self._engine.connect() as conn:
            ids = [i for p in record.void_plans for i in p.waybill_ids]
            waybills = {w["id"]: w for w in waybill_store.by_ids(conn, ids)}
            orders = {o["id"]: o for o in order_store.get_by_ids(
                conn, [w["order_id"] for w in waybills.values()])}
        shops = []
        for plan in record.void_plans:
            items = []
            for wid in plan.waybill_ids:
                w = waybills[wid]
                items.append({
                    "waybill_id": wid, "order_id": w["order_id"],
                    "order_no": orders[w["order_id"]]["order_no"],
                    "courier_code": w["courier_code"], "waybill_no": w["waybill_no"],
                })
            shops.append({"shop_id": plan.shop_id, "shop_name": plan.shop_name,
                          "waybills": items})
        return {
            "preview_id": record.preview_id, "mode": record.mode,
            "shops": shops,
            "blocked": [vars(b) for b in record.blocked],
            "shop_errors": [vars(e) for e in record.shop_errors],
            "total_ready": len(ids),
            "total_blocked": len(record.blocked),
            "dry_run": record.dry_run,
        }

    # ---- 内部 ----

    @staticmethod
    def _check_mode(mode: str, allowed: tuple[str, ...]) -> None:
        if mode not in allowed:
            raise InvalidRequest(f"不支持的预览类型: {mode}")

    @staticmethod
    def _load_orders(conn, order_ids: Sequence[int]) -> list[dict[str, Any]]:
        rows = order_store.get_by_ids(conn, order_ids)
        found = {r["id"] for r in rows}
        missing = [i for i in order_ids if i not in found]
        if missing:
            raise NotFound(f"订单不存在: {missing[0]}", None)
        return rows

    @staticmethod
    def _group(rows: Sequence[Mapping[str, Any]]) -> dict[int, list[Mapping[str, Any]]]:
        out: dict[int, list[Mapping[str, Any]]] = {}
        for r in rows:
            out.setdefault(r["shop_id"], []).append(r)
        return out

    @staticmethod
    def _shop_plan(conn, shop, preferred: str | None):
        """返回 (plan, None) 或 (None, 原因)。shop 级问题整店阻断。"""
        if shop["status"] != "active":
            return None, "店铺未登录或已停用"
        if shop["paused_reason"]:
            return None, "店铺已暂停，请先恢复"
        addresses = base_data_store.list_addresses(conn, shop["id"])
        default = next((a for a in addresses if a["is_default"]), None)
        if default is None:
            return None, "没有默认发货地址"
        templates = base_data_store.list_templates(conn, shop["id"])
        accounts = base_data_store.list_ebill_accounts(conn, shop["id"])
        courier = pick_courier(templates, accounts, preferred)
        if courier is None:
            return None, "没有同时具备面单模板和可用面单账户的快递"
        if preferred and courier != preferred:
            return None, f"快递 {preferred} 没有面单模板或可用面单账户"
        account = select_account(accounts, courier)
        if account is None:  # pick_courier 已保证存在，防御
            return None, "没有可用的面单账户"
        templates_for = sorted(
            (t for t in templates if t["courier_code"] == courier),
            key=lambda t: (not t["is_custom"], t["template_code"]),
        )
        if not templates_for:
            return None, f"快递 {courier} 没有面单模板"
        couriers = {
            c["courier_code"]: c["name"]
            for c in base_data_store.list_couriers(conn, shop["id"])
        }
        return {
            "courier_code": courier, "courier_name": couriers.get(courier),
            "template_code": templates_for[0]["template_code"],
            "ebill_id": account["ebill_id"], "net_code": account["net_code"],
            "account_balance": account["balance"], "address": default,
        }, None

    @staticmethod
    def _void_blocker(order: Mapping[str, Any], active: Mapping[str, Any] | None) -> str | None:
        if order["status"] not in VOIDABLE_STATUSES:
            return f"本地状态为 {order['status']}，不可作废"
        if active is None:
            return "没有有效面单"
        return None

    def _mark_pending(self, conn, record: PreviewRecord) -> None:
        """预检通过的 synced 订单转 pending_label（data-model 6.1）；已入库的写库失败不影响预览。"""
        ready = [oid for p in record.shops for oid in p.order_ids]
        if not ready:
            return
        now = self._clock().strftime(_ISO_FMT)
        with self._engine.begin() as wconn:
            for row in order_store.get_by_ids(conn, ready):
                if row["status"] == LocalOrderStatus.SYNCED.value:
                    order_store.set_local_status(
                        wconn, row["shop_id"], row["order_no"], LocalOrderStatus.PENDING_LABEL, now
                    )
