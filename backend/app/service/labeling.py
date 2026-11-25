"""两步提交第③步：按预览执行取号 / 一体 / 作废（backend 5.5 / 5.11 / 5.12、flows 7.3）。

逐店串行（同一店经 ShopRunner 队列）；每一单先按幂等键登记任务：
已成功的直接复用结果，运行中的跳过，失败 / 待核实的复用任务行重试。
取号超时或「不存在可取号商品」不转 exception，而是查回运单号（label_recovery）。
具体协议处理在 label_obtain / label_void，写库与事件在 label_run。
演练模式下不进入状态机、不发写请求，只把「将发出的请求」记入审计并返回模拟汇总。
"""

from collections.abc import Callable
from datetime import datetime

import structlog
from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.domain.errors import InvalidRequest
from app.service import dry_run
from app.service.background import TaskRegistry
from app.service.events import LABEL_DONE, EventBus
from app.service.label_obtain import ObtainRunner
from app.service.label_preview import (
    MODE_FETCH_AND_SHIP,
    MODE_VOID,
    LabelPreviewService,
    PreviewRecord,
    ShopPlan,
)
from app.service.label_run import Counter, ExecuteStarted, RunContext, RunSummary, utc_now
from app.service.label_void import VoidRunner
from app.service.shop_runner import ShopRunner
from app.store import order_store, waybill_store

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
        self._clock = clock
        self._ctx = RunContext(engine, runner, events, printer_name, clock)
        self._obtain = ObtainRunner(self._ctx)
        self._void = VoidRunner(self._ctx)

    # ---- 入口 ----

    async def execute_inline(
        self, preview_id: str, actor: str, expected_mode: str | None = None
    ) -> RunSummary:
        """同步执行（测试与后台共用）。"""
        record = self._take(preview_id, actor, expected_mode)
        if self._is_dry(record):
            return self._simulate(record)
        return await self._run(record)

    def execute(
        self, preview_id: str, actor: str, expected_mode: str | None = None
    ) -> ExecuteStarted:
        record = self._take(preview_id, actor, expected_mode)
        if self._is_dry(record):
            self._simulate(record)
            return ExecuteStarted(
                record.preview_id, record.mode, self._shop_ids(record), simulated=True)
        self._tasks.spawn(f"labels-{preview_id}", self._run(record))
        return ExecuteStarted(record.preview_id, record.mode, self._shop_ids(record))

    def _take(
        self, preview_id: str, actor: str, expected_mode: str | None = None
    ) -> PreviewRecord:
        record = self._previews.previews.take(preview_id, actor)
        if expected_mode is not None and record.mode != expected_mode:
            raise InvalidRequest("预览类型与执行入口不一致，请重新预览")
        return record

    def _is_dry(self, record: PreviewRecord) -> bool:
        return self._dry_run or record.dry_run

    # ---- 演练模式：只记审计，不发写请求 ----

    def _simulate(self, record: PreviewRecord) -> RunSummary:
        counter = Counter()
        intents: list[dry_run.Intent] = []
        if record.mode == MODE_VOID:
            intents.extend(self._simulate_void(record, counter))
        else:
            intents.extend(self._simulate_obtain(record, counter))
        dry_run.record(self._engine, intents, self._clock)
        summary = counter.summary()
        self._events.publish(LABEL_DONE, {
            "preview_id": record.preview_id, "mode": record.mode,
            "simulated": True, **vars(summary),
        })
        return summary

    def _simulate_obtain(
        self, record: PreviewRecord, counter: Counter,
    ) -> list[dry_run.Intent]:
        endpoint = (
            ep.LABEL_FETCH_AND_SHIP
            if record.mode == MODE_FETCH_AND_SHIP else ep.LABEL_FETCH)
        all_ids = [oid for p in record.shops for oid in p.order_ids]
        rows = {r["id"]: r for r in self._ctx.reload(all_ids)[0]}
        intents: list[dry_run.Intent] = []
        for plan in record.shops:
            order_nos = [rows[i]["order_no"] for i in plan.order_ids if i in rows]
            intents.append(dry_run.Intent(
                action=endpoint.name, actor=record.actor, shop_id=plan.shop_id,
                request={
                    "endpoint": endpoint.path, "mode": record.mode,
                    "courier_code": plan.courier_code,
                    "template_code": plan.template_code,
                    "ebill_id": plan.ebill_id, "net_code": plan.net_code,
                    "printer": self._ctx.printer, "order_nos": order_nos,
                },
            ))
            for oid in plan.order_ids:
                row = rows.get(oid)
                if row is not None:
                    counter.skipped += 1
                    self._ctx.publish(record, row, "skipped", reason=dry_run.REASON)
        return intents

    def _simulate_void(
        self, record: PreviewRecord, counter: Counter,
    ) -> list[dry_run.Intent]:
        ids = [wid for p in record.void_plans for wid in p.waybill_ids]
        with self._engine.connect() as conn:
            waybills = {w["id"]: w for w in waybill_store.by_ids(conn, ids)}
            orders = {o["id"]: o for o in order_store.get_by_ids(
                conn, [w["order_id"] for w in waybills.values()])}
        intents: list[dry_run.Intent] = []
        for plan in record.void_plans:
            items = [waybills[i] for i in plan.waybill_ids if i in waybills]
            intents.append(dry_run.Intent(
                action=ep.CANCEL_TRACKING_NOS.name, actor=record.actor,
                shop_id=plan.shop_id,
                request={
                    "endpoint": ep.CANCEL_TRACKING_NOS.path,
                    "waybills": [
                        {"courier_code": w["courier_code"], "tracking_no": w["waybill_no"]}
                        for w in items
                    ],
                },
            ))
            for waybill in items:
                order = orders.get(waybill["order_id"]) or {
                    "order_no": str(waybill["order_id"])}
                counter.skipped += 1
                self._ctx.publish(record, order, "skipped", reason=dry_run.REASON)
        return intents

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
