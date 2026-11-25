"""发货批次的目标读取与分组（service 只读助手，backend 5.6）。

把「选中的本地订单」变成可发货目标：有效面单 + 店铺名；不可发货的订单带阻断原因返回。
纯读本地库，不发请求；协议请求构造与解析在 adapter/doudian。
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.shipping_parsers import parse_sendcheck_result
from app.adapter.doudian.shipping_request import sendcheck_body
from app.domain.errors import InvalidRequest, NotFound
from app.domain.models import SendCheckResult
from app.domain.shipping_rules import ship_blockers
from app.store import base_data_store, order_store, shipping_store, shop_store, waybill_store


@dataclass(frozen=True)
class ShipTarget:
    order_id: int
    order_no: str
    shop_id: int
    shop_name: str
    waybill_id: int
    courier_code: str
    tracking_no: str


@dataclass(frozen=True)
class BlockedShip:
    order_id: int
    order_no: str
    shop_name: str
    reason: str


@dataclass
class PackageGroup:
    shop_id: int
    courier_code: str
    tracking_no: str
    targets: list[ShipTarget] = field(default_factory=list)


def load_targets(
    engine: Engine, order_ids: Sequence[int],
) -> tuple[list[ShipTarget], list[BlockedShip]]:
    unique: list[int] = list(dict.fromkeys(int(i) for i in order_ids))
    if not unique:
        raise InvalidRequest("请选择要发货的订单")
    with engine.connect() as conn:
        rows = {r["id"]: r for r in order_store.get_by_ids(conn, unique)}
        missing = [i for i in unique if i not in rows]
        if missing:
            raise NotFound(f"订单不存在: {missing[0]}")
        active = waybill_store.active_by_orders(conn, unique)
        names = {s["id"]: s["name"] for s in shop_store.list(conn)}
    targets: list[ShipTarget] = []
    blocked: list[BlockedShip] = []
    for oid in unique:
        row = rows[oid]
        waybill = active.get(oid)
        waybill_no = waybill["waybill_no"] if waybill else None
        reasons = ship_blockers(
            row["status"], waybill["status"] if waybill else None, waybill_no)
        if reasons or waybill is None or not waybill_no:
            blocked.append(BlockedShip(
                oid, row["order_no"], names.get(row["shop_id"], ""), "；".join(reasons)))
            continue
        targets.append(ShipTarget(
            oid, row["order_no"], row["shop_id"], names.get(row["shop_id"], ""),
            waybill["id"], waybill["courier_code"], waybill_no,
        ))
    return targets, blocked


def default_address(engine: Engine, shop_id: int) -> dict | None:
    with engine.connect() as conn:
        addresses = base_data_store.list_addresses(conn, shop_id)
    if not addresses:
        return None
    return next((a for a in addresses if a["is_default"]), addresses[0])


def group_packages(targets: Sequence[ShipTarget]) -> list[PackageGroup]:
    """同一 (店, 快递, 运单号) 是一个包裹；一个包裹可覆盖多个订单。"""
    groups: dict[tuple[int, str, str], PackageGroup] = {}
    for target in targets:
        key = (target.shop_id, target.courier_code, target.tracking_no)
        package = groups.get(key)
        if package is None:
            package = groups[key] = PackageGroup(
                target.shop_id, target.courier_code, target.tracking_no)
        package.targets.append(target)
    return list(groups.values())


def pool_view(
    engine: Engine, shop_ids: Sequence[int] | None, page: int, page_size: int,
) -> tuple[list[dict], int]:
    """发货台订单池的展示行（附店铺名与运单号）。"""
    with engine.connect() as conn:
        rows, total = shipping_store.list_pool(conn, shop_ids, page, page_size)
        names = {s["id"]: s["name"] for s in shop_store.list(conn)}
    items = [
        {
            "id": r["id"], "shop_id": r["shop_id"],
            "shop_name": names.get(r["shop_id"], ""), "order_no": r["order_no"],
            "status": r["status"], "platform_status": r["platform_status"],
            "amount_cents": r["amount_cents"], "pay_time": r["pay_time"],
            "exp_ship_time": r["exp_ship_time"],
            "waybill_id": r["waybill_id"], "courier_code": r["courier_code"],
            "tracking_no": r["waybill_no"],
            "printed": r["status"] == "printed",
        }
        for r in rows
    ]
    return items, total


def call_sendcheck(order_nos: Sequence[str], address: dict):
    async def job(client: FxgClient) -> SendCheckResult:
        resp = await client.call(ep.SEND_CHECK, body=sendcheck_body(order_nos, address))
        return parse_sendcheck_result(resp)

    return job


def describe(exc: Exception) -> str:
    return str(exc) or type(exc).__name__
