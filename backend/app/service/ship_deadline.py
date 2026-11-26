"""ENG-07：临近发货超时告警（只读本地订单，不请求抖店）。

扫描未发货的订单：`exp_ship_time` 距现在不足 N 小时（含已超时）的，按最紧急排序，
发布 `ship_deadline_warning` SSE 事件，由 NotificationFeed 翻译成临近超时通知（状态类）。
每次扫描都发布（数量为 0 时通知据此恢复），无需持久化。
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import Engine

from app.domain.order_status import LocalOrderStatus
from app.service.events import SHIP_DEADLINE_WARNING, EventBus
from app.store import order_store, shop_store

log = structlog.get_logger()

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_WARN_HOURS = 6
DEFAULT_LIMIT = 200
# 只有这些本地状态的订单还值得催发货；已发货 / 已取消 / 异常单不进告警
PENDING_STATUSES = (
    LocalOrderStatus.SYNCED.value,
    LocalOrderStatus.PENDING_LABEL.value,
    LocalOrderStatus.LABEL_OBTAINED.value,
    LocalOrderStatus.PRINTED.value,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class ShipDeadlineWatcher:
    def __init__(
        self, engine: Engine, events: EventBus, *, warn_hours: int = DEFAULT_WARN_HOURS,
        limit: int = DEFAULT_LIMIT, clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._engine = engine
        self._events = events
        self._warn_hours = warn_hours
        self._limit = limit
        self._clock = clock

    def scan(self) -> dict:
        now = self._clock()
        warn_until = (now + timedelta(hours=self._warn_hours)).strftime(ISO_FMT)
        with self._engine.connect() as conn:
            rows = order_store.ship_deadline_due(conn, PENDING_STATUSES, warn_until, self._limit)
            # items 截到上限；分店真实数量另算，供通知按店对账
            shop_counts = order_store.ship_deadline_counts(conn, PENDING_STATUSES, warn_until)
            # 已超时的分店数量：通知据此跳「已超时」筛选
            shop_overdue = order_store.ship_deadline_counts(
                conn, PENDING_STATUSES, now.strftime(ISO_FMT), before=True)
            names = {s["id"]: s["name"] for s in shop_store.list(conn)}
        items = [
            {
                "shop_id": row["shop_id"],
                "shop_name": names.get(row["shop_id"], ""),
                "order_no": row["order_no"],
                "status": row["status"],
                "exp_ship_time": row["exp_ship_time"],
            }
            for row in rows
        ]
        self._events.publish(SHIP_DEADLINE_WARNING, {
            "count": len(items),
            "warn_hours": self._warn_hours,
            "checked_at": now.strftime(ISO_FMT),
            "items": items,
            "shop_counts": shop_counts,
            "shop_overdue": shop_overdue,
        })
        if items:
            log.info("ship_deadline.warning", count=len(items), warn_hours=self._warn_hours)
        return {"count": len(items), "items": items}
