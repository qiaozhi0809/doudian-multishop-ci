"""发货服务的视图 / 结果数据类型（shipping.py 只保留编排逻辑）。"""

from dataclasses import dataclass

from app.domain.models import SendCheckResult
from app.service.shipping_plan import BlockedShip, ShipTarget


@dataclass(frozen=True)
class ShopCheck:
    shop_id: int
    shop_name: str
    order_nos: tuple[str, ...]
    result: SendCheckResult


@dataclass(frozen=True)
class ShopCheckError:
    shop_id: int
    shop_name: str
    reason: str


@dataclass(frozen=True)
class CheckView:
    shops: tuple[ShopCheck, ...]
    blocked: tuple[BlockedShip, ...]
    shop_errors: tuple[ShopCheckError, ...]
    targets: tuple[ShipTarget, ...] = ()

    @property
    def double_check_total(self) -> int:
        return sum(s.result.double_check_num for s in self.shops)


@dataclass(frozen=True)
class ShipStarted:
    batch_id: str
    shop_ids: list[int]
    package_count: int
    order_count: int
    simulated: bool = False  # 演练模式：没有发出真实发货请求


@dataclass(frozen=True)
class ShipSummary:
    ok: int = 0
    failed: int = 0
    skipped: int = 0


@dataclass
class Counter:
    ok: int = 0
    failed: int = 0
    skipped: int = 0

    def summary(self) -> ShipSummary:
        return ShipSummary(self.ok, self.failed, self.skipped)
