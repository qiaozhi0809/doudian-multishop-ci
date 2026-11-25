"""取号执行的共享上下文：汇总计数、进度事件、任务 / 面单 / 订单的统一写入。

取号与作废两个执行器（label_obtain / label_void）共用这里的写库与事件逻辑，
保证状态推进只有一处实现（backend 5.11 / data-model 6.1）。
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy import Engine

from app.domain.idempotency import label_key, next_seq, void_key
from app.domain.models import FetchSuccess
from app.domain.order_status import LocalOrderStatus
from app.domain.task_status import TaskStatus, TaskType
from app.service.events import LABEL_PROGRESS, EventBus
from app.service.label_preview import MODE_FETCH_AND_SHIP, MODE_OBTAIN, PreviewRecord, ShopPlan
from app.service.shop_runner import ShopRunner
from app.store import order_store, task_store, waybill_store

DEFAULT_EXP_TYPE = "defaultProductType"  # A.2.7：普快为默认产品类型
LABEL_NOT_FOUND_MSG = "不存在可取号商品"
RECOVERY_MISS_REASON = "取号结果不明，已登记待核实（未查回运单号）"
PARTIAL_RESULT_REASON = "平台未返回该订单的取号结果"
VOID_UNKNOWN_REASON = "作废结果不明，请到平台核对后再操作"
DUPLICATE_WAYBILL_REASON = "运单号已存在，无法写入"
BUSY_LABEL_REASON = "同一订单的取号正在执行"
BUSY_VOID_REASON = "同一面单的作废正在执行"
CHANGED_REASON = "面单或订单状态已变化"
_PRINTER_UNSET = ""
_TASK_TYPE_BY_MODE = {
    MODE_OBTAIN: TaskType.OBTAIN_LABEL,
    MODE_FETCH_AND_SHIP: TaskType.FETCH_AND_SHIP,
}
ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class RunSummary:
    ok: int = 0
    failed: int = 0
    verifying: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class ExecuteStarted:
    preview_id: str
    mode: str
    shop_ids: list[int]


@dataclass
class Counter:
    ok: int = 0
    failed: int = 0
    verifying: int = 0
    skipped: int = 0

    def summary(self) -> RunSummary:
        return RunSummary(self.ok, self.failed, self.verifying, self.skipped)


class RunContext:
    """一次执行共享的引擎、任务入口、事件与写入助手。"""

    def __init__(
        self, engine: Engine, runner: ShopRunner, events: EventBus,
        printer_name: str = _PRINTER_UNSET, clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.engine = engine
        self.runner = runner
        self.events = events
        self.printer = printer_name or None
        self._clock = clock

    # ---- 读库 ----

    def reload(self, order_ids) -> tuple[list[dict], dict]:
        with self.engine.connect() as conn:
            rows = order_store.get_by_ids(conn, list(order_ids))
            items = order_store.items_by_order(conn, [r["id"] for r in rows])
        return rows, items

    def active_waybills(self, order_ids) -> dict[int, dict]:
        with self.engine.connect() as conn:
            return waybill_store.active_by_orders(conn, order_ids)

    def order_ids_for_waybills(self, waybill_ids) -> list[int]:
        with self.engine.connect() as conn:
            return [w["order_id"] for w in waybill_store.by_ids(conn, list(waybill_ids))]

    @staticmethod
    def plan_of(record: PreviewRecord, shop_id: int) -> ShopPlan:
        return next(p for p in record.shops if p.shop_id == shop_id)

    def now(self) -> str:
        return self._clock().strftime(ISO_FMT)

    # ---- 事件 ----

    def publish(self, record: PreviewRecord, row: dict, result: str,
                tracking_no: str | None = None, reason: str | None = None) -> None:
        self.events.publish(LABEL_PROGRESS, {
            "preview_id": record.preview_id, "mode": record.mode,
            "shop_id": row.get("shop_id"), "order_id": row.get("id"),
            "order_no": row.get("order_no"), "result": result,
            "tracking_no": tracking_no, "reason": reason,
        })

    # ---- 任务登记（幂等键） ----

    def prepare_label_task(self, row: dict, mode: str, actor: str) -> tuple[str, dict, int]:
        now = self.now()
        with self.engine.begin() as conn:
            seq = next_seq(waybill_store.voided_count(conn, row["id"]))
            key = label_key(row["shop_id"], row["order_no"], seq)
            existing = task_store.get_by_key(conn, key)
            if existing and existing["status"] in (
                TaskStatus.RUNNING.value, TaskStatus.QUEUED.value
            ):
                return "busy", existing, seq
            task = task_store.start(
                conn, key=key, shop_id=row["shop_id"], type=_TASK_TYPE_BY_MODE[mode].value,
                payload={"order_id": row["id"], "seq": seq}, actor=actor, now=now,
            )
        return ("done" if task["status"] == TaskStatus.SUCCESS.value else "started",
                task, seq)

    def prepare_void_task(self, waybill: dict, actor: str) -> tuple[str, dict]:
        now = self.now()
        key = void_key(waybill["shop_id"], waybill["courier_code"], waybill["waybill_no"])
        with self.engine.begin() as conn:
            existing = task_store.get_by_key(conn, key)
            if existing and existing["status"] in (
                TaskStatus.RUNNING.value, TaskStatus.QUEUED.value
            ):
                return "busy", existing
            task = task_store.start(
                conn, key=key, shop_id=waybill["shop_id"], type=TaskType.VOID_LABEL.value,
                payload={"waybill_id": waybill["id"]}, actor=actor, now=now,
            )
        return ("done" if task["status"] == TaskStatus.SUCCESS.value else "started", task)

    # ---- 状态写入 ----

    def record_success(
        self, record: PreviewRecord, plan: ShopPlan, row: dict, task: dict, seq: int,
        success: FetchSuccess, counter: Counter, exp_type: str | None = None,
    ) -> None:
        now = self.now()
        target = (LocalOrderStatus.SHIPPED if record.mode == MODE_FETCH_AND_SHIP
                  else LocalOrderStatus.LABEL_OBTAINED)
        try:
            with self.engine.begin() as conn:
                wid = conn.execute(sa.select(waybill_store.waybills.c.id).where(
                    waybill_store.waybills.c.order_id == row["id"],
                    waybill_store.waybills.c.status.in_(waybill_store.ACTIVE_STATUSES),
                )).scalar()
                if wid is None:
                    waybill_store.insert(
                        conn, shop_id=row["shop_id"], order_id=row["id"], seq=seq,
                        courier_code=success.courier_code or plan.courier_code,
                        waybill_no=success.tracking_no,
                        print_data=success.print_data, sign=success.sign,
                        template_code=success.template_code or plan.template_code,
                        exp_type=exp_type, ebill_id=plan.ebill_id, net_code=plan.net_code,
                        status="active", now=now,
                    )
                order_store.set_local_status(
                    conn, row["shop_id"], row["order_no"], target, now)
                task_store.finish(conn, task["id"], TaskStatus.SUCCESS, None, now)
        except sa.exc.IntegrityError:
            # 运单号或有效面单冲突：多为另一个执行已写入，复用现有面单
            self._reuse_active(record, row, task, target, counter)
            return
        counter.ok += 1
        self.publish(record, row, "success", tracking_no=success.tracking_no)

    def _reuse_active(self, record: PreviewRecord, row: dict, task: dict,
                      target: LocalOrderStatus, counter: Counter) -> None:
        now = self.now()
        with self.engine.begin() as conn:
            active = waybill_store.active_by_orders(conn, [row["id"]]).get(row["id"])
            if active is None:
                task_store.finish(conn, task["id"], TaskStatus.FAILED,
                                  DUPLICATE_WAYBILL_REASON, now)
            else:
                order_store.set_local_status(
                    conn, row["shop_id"], row["order_no"], target, now)
                task_store.finish(conn, task["id"], TaskStatus.SUCCESS, None, now)
        if active is None:
            counter.failed += 1
            self.publish(record, row, "failed", reason=DUPLICATE_WAYBILL_REASON)
        else:
            counter.ok += 1
            self.publish(record, row, "success", tracking_no=active["waybill_no"])

    def record_void(self, order: dict, task: dict, waybill: dict, counter: Counter,
                    record: PreviewRecord) -> None:
        now = self.now()
        with self.engine.begin() as conn:
            waybill_store.mark_void(conn, waybill["id"], now)
            order_store.set_local_status(
                conn, order["shop_id"], order["order_no"], LocalOrderStatus.PENDING_LABEL, now)
            task_store.finish(conn, task["id"], TaskStatus.SUCCESS, None, now)
        counter.ok += 1
        self.publish(record, order, "success", tracking_no=waybill["waybill_no"])

    def finish_failed(self, record: PreviewRecord, row: dict, task: dict,
                      counter: Counter, reason: str) -> None:
        now = self.now()
        with self.engine.begin() as conn:
            task_store.finish(conn, task["id"], TaskStatus.FAILED, reason, now)
            current = conn.execute(sa.select(order_store.orders.c.status).where(
                order_store.orders.c.id == row["id"])).scalar()
            if current in (LocalOrderStatus.SYNCED.value, LocalOrderStatus.PENDING_LABEL.value):
                order_store.mark_exception(conn, row["shop_id"], row["order_no"], reason, now)
        counter.failed += 1
        self.publish(record, row, "failed", reason=reason)

    def finish_verifying(self, record: PreviewRecord, row: dict, task: dict,
                         counter: Counter, reason: str) -> None:
        now = self.now()
        with self.engine.begin() as conn:
            task_store.finish(conn, task["id"], TaskStatus.VERIFYING, reason, now)
        counter.verifying += 1
        self.publish(record, row, "verifying", reason=RECOVERY_MISS_REASON)
