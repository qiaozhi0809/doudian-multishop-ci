"""发货演练模式（overview 14.11）：只组装「将发出的请求」，不做任何网络调用。

拆成独立模块，一是让 shipping.py 保持在文件长度上限内，
二是让「演练不发请求」的边界一眼可见：这里没有任何 client / runner 入口。
"""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.domain.errors import InvalidRequest
from app.service import dry_run
from app.service.shipping_plan import PackageGroup, ShipTarget, group_packages, load_targets


@dataclass(frozen=True)
class DryRunShipPlan:
    targets: tuple[ShipTarget, ...]
    packages: tuple[PackageGroup, ...]
    intents: tuple[dry_run.Intent, ...]


def plan(engine: Engine, order_ids: Sequence[int], actor: str) -> DryRunShipPlan:
    targets, _blocked = load_targets(engine, order_ids)
    if not targets:
        raise InvalidRequest("没有可发货的订单")
    packages = group_packages(targets)
    intents: list[dry_run.Intent] = []
    for shop_id in sorted({p.shop_id for p in packages}):
        shop_packages = [p for p in packages if p.shop_id == shop_id]
        intents.append(dry_run.Intent(
            action=ep.BATCH_DELIVER.name, actor=actor, shop_id=shop_id,
            request={
                "endpoint": ep.BATCH_DELIVER.path,
                "send_type": "3",
                "batch_deliver_packages": [
                    {"logistics_company_code": p.courier_code, "tracking_no": p.tracking_no}
                    for p in shop_packages
                ],
            },
        ))
    intents.append(dry_run.Intent(
        action="ship_batch", actor=actor,
        request={"orders": len(targets), "packages": len(packages)},
    ))
    return DryRunShipPlan(tuple(targets), tuple(packages), tuple(intents))
