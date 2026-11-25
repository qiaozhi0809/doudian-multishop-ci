"""两步提交第③步：按预览执行取号 / 一体 / 作废（backend 5.5 / 5.11 / 5.12、flows 7.3）。

逐店串行（同一店经 ShopRunner 队列）；每一单先按幂等键登记任务：
已成功的直接复用结果，运行中的跳过，失败 / 待核实的复用任务行重试。
取号超时或「不存在可取号商品」不转 exception，而是查回运单号（label_recovery）。
具体协议处理在 label_obtain / label_void，写库与事件在 label_run。
"""

from collections.abc import Callable
from datetime import datetime

import structlog
from sqlalchemy import Engine

from app.domain.errors import DryRunBlocked, InvalidRequest
from app.service.background import TaskRegistry
from app.service.events import LABEL_DONE, EventBus
from app.service.label_obtain import ObtainRunner
from app.service.label_preview import (
    MODE_VOID,
    LabelPreviewService,
    PreviewRecord,
    ShopPlan,
)
from app.service.label_run import Counter, ExecuteStarted, RunContext, RunSummary, utc_now
from app.service.label_void import VoidRunner
from app.service.shop_runner import ShopRunner
from app.store import order_store

log = structlog.get_logger()


class LabelingService:
    def __init__(
        self, engine: Engine, runner: ShopRunner, previews: LabelPreviewService,
        events: EventBus, *, printer_name: str = "", dry_run: bool = False,
        tasks: TaskRegistry | None = None, clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._engine = engine
        self._previews = previews
        self._events = events
        self._dry_run = dry_run
        self._tasks = tasks or TaskRegistry()
        self._ctx = RunContext(engine, runner, events, printer_name, clock)
        self._obtain = ObtainRunner(self._ctx)
        self._void = VoidRunner(self._ctx)

    # ---- 入口 ----

    async def execute_inline(
        self, preview_id: str, actor: str, expected_mode: str | None = None
    ) -> RunSummary:
        """同步执行（测试与后台共用）。"""
        return await self._run(self._take(preview_id, actor, expected_mode))

    def execute(
        self, preview_id: str, actor: str, expected_mode: str | None = None
    ) -> ExecuteStarted:
        record = self._take(preview_id, actor, expected_mode)
        self._tasks.spawn(f"labels-{preview_id}", self._run(record))
        return ExecuteStarted(record.preview_id, record.mode, self._shop_ids(record))

    def _take(
        self, preview_id: str, actor: str, expected_mode: str | None = None
    ) -> PreviewRecord:
        record = self._previews.previews.take(preview_id, actor)
        if expected_mode is not None and record.mode != expected_mode:
            raise InvalidRequest("预览类型与执行入口不一致，请重新预览")
        if self._dry_run or record.dry_run:
            raise DryRunBlocked("演练模式下不能执行写操作")
        return record

    @staticmethod
    def _shop_ids(record: PreviewRecord) -> list[int]:
        if record.mode == MODE_VOID:
            return [p.shop_id for p in record.void_plans]
        return [p.shop_id for p in record.shops]

    async def _run(self, record: PreviewRecord) -> RunSummary:
        counter = Counter()
        if record.mode == MODE_VOID:
            for plan in record.void_plans:
                try:
                    await self._void.run_shop(record, plan, counter)
                except Exception as e:  # 单店失败隔离
                    self._shop_failed(record, plan, counter, e)
        else:
            for plan in record.shops:
                try:
                    await self._obtain.run_shop(record, plan, counter)
                except Exception as e:
                    self._shop_failed(record, plan, counter, e)
        summary = counter.summary()
        self._events.publish(LABEL_DONE, {"preview_id": record.preview_id,
                                          "mode": record.mode, **vars(summary)})
        return summary

    def _shop_failed(self, record: PreviewRecord, plan, counter: Counter,
                     exc: Exception) -> None:
        reason = str(exc) or type(exc).__name__
        log.warning("labeling.shop_failed", shop_id=plan.shop_id, error=type(exc).__name__)
        order_ids = (plan.order_ids if isinstance(plan, ShopPlan)
                     else self._ctx.order_ids_for_waybills(plan.waybill_ids))
        with self._engine.connect() as conn:
            rows = {r["id"]: r for r in order_store.get_by_ids(conn, list(order_ids))}
        for oid in order_ids:
            row = rows.get(oid)
            if row:
                counter.failed += 1
                self._ctx.publish(record, row, "failed", reason=reason)
