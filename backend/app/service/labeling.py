"""两步提交第③步：按预览执行取号 / 一体 / 作废（backend 5.5 / 5.11 / 5.12、flows 7.3）。

逐店串行（同一店经 ShopRunner 队列）；每一单先按幂等键登记任务：
已成功的直接复用结果，运行中的跳过，失败 / 待核实的复用任务行重试。
取号超时或「不存在可取号商品」不转 exception，而是查回运单号（label_recovery）。
"""

from dataclasses import dataclass
from datetime import UTC, datetime

import sqlalchemy as sa
import structlog
from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.errors import (
    BizRejected,
    ParseError,
    TransientError,
)
from app.adapter.doudian.label_parsers import (
    parse_cancel_result,
    parse_fetch_and_ship_result,
    parse_fetch_result,
    parse_product_types,
)
from app.adapter.doudian.label_request import (
    cancel_body,
    fetch_and_ship_body,
    obtain_body,
    order_list_payload,
)
from app.domain.errors import DryRunBlocked
from app.domain.idempotency import label_key, next_seq, void_key
from app.domain.labeling_rules import VOIDABLE_STATUSES, order_blockers
from app.domain.models import FetchSuccess
from app.domain.order_status import LocalOrderStatus
from app.domain.task_status import TaskStatus, TaskType
from app.service.background import TaskRegistry
from app.service.events import LABEL_DONE, LABEL_PROGRESS, EventBus
from app.service.label_preview import (
    MODE_FETCH_AND_SHIP,
    MODE_OBTAIN,
    MODE_VOID,
    LabelPreviewService,
    PreviewRecord,
    ShopPlan,
    VoidPlan,
)
from app.service.label_recovery import find_tracking_no
from app.service.shop_runner import ShopRunner
from app.store import order_store, task_store, waybill_store

log = structlog.get_logger()

DEFAULT_EXP_TYPE = "defaultProductType"  # A.2.7：普快为默认产品类型
LABEL_NOT_FOUND_MSG = "不存在可取号商品"
RECOVERY_MISS_REASON = "取号结果不明，已登记待核实（未查回运单号）"
PARTIAL_RESULT_REASON = "平台未返回该订单的取号结果"
VOID_UNKNOWN_REASON = "作废结果不明，请到平台核对后再操作"
_PRINTER_UNSET = ""
_TASK_TYPE_BY_MODE = {
    MODE_OBTAIN: TaskType.OBTAIN_LABEL,
    MODE_FETCH_AND_SHIP: TaskType.FETCH_AND_SHIP,
}
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


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
class _Counter:
    ok: int = 0
    failed: int = 0
    verifying: int = 0
    skipped: int = 0

    def summary(self) -> RunSummary:
        return RunSummary(self.ok, self.failed, self.verifying, self.skipped)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class LabelingService:
    def __init__(
        self, engine: Engine, runner: ShopRunner, previews: LabelPreviewService,
        events: EventBus, *, printer_name: str = _PRINTER_UNSET, dry_run: bool = False,
        tasks: TaskRegistry | None = None, clock=_utc_now,
    ) -> None:
        self._engine = engine
        self._runner = runner
        self._previews = previews
        self._events = events
        self._printer = printer_name or None
        self._dry_run = dry_run
        self._tasks = tasks or TaskRegistry()
        self._clock = clock

    # ---- 入口 ----

    async def execute_inline(self, preview_id: str, actor: str) -> RunSummary:
        """同步执行（测试与后台共用）。"""
        return await self._run(self._take(preview_id, actor))

    def execute(self, preview_id: str, actor: str) -> ExecuteStarted:
        record = self._take(preview_id, actor)
        self._tasks.spawn(f"labels-{preview_id}", self._run(record))
        return ExecuteStarted(record.preview_id, record.mode, self._shop_ids(record))

    def _take(self, preview_id: str, actor: str) -> PreviewRecord:
        record = self._previews.previews.take(preview_id, actor)
        if self._dry_run or record.dry_run:
            raise DryRunBlocked("演练模式下不能执行写操作")
        return record

    @staticmethod
    def _shop_ids(record: PreviewRecord) -> list[int]:
        if record.mode == MODE_VOID:
            return [p.shop_id for p in record.void_plans]
        return [p.shop_id for p in record.shops]

    async def _run(self, record: PreviewRecord) -> RunSummary:
        counter = _Counter()
        if record.mode == MODE_VOID:
            for plan in record.void_plans:
                try:
                    await self._run_void_shop(record, plan, counter)
                except Exception as e:  # 单店失败隔离
                    self._shop_failed(record, plan, counter, e)
        else:
            for plan in record.shops:
                try:
                    await self._run_obtain_shop(record, plan, counter)
                except Exception as e:
                    self._shop_failed(record, plan, counter, e)
        summary = counter.summary()
        self._events.publish(LABEL_DONE, {"preview_id": record.preview_id,
                                          "mode": record.mode, **vars(summary)})
        return summary

    def _shop_failed(self, record: PreviewRecord, plan, counter: _Counter, exc: Exception) -> None:
        reason = str(exc) or type(exc).__name__
        log.warning("labeling.shop_failed", shop_id=plan.shop_id, error=type(exc).__name__)
        order_ids = (plan.order_ids if isinstance(plan, ShopPlan)
                     else self._order_ids_for_waybills(plan.waybill_ids))
        with self._engine.connect() as conn:
            rows = {r["id"]: r for r in order_store.get_by_ids(conn, list(order_ids))}
        for oid in order_ids:
            row = rows.get(oid)
            if row:
                counter.failed += 1
                self._publish(record, row, "failed", reason=reason)

    # ---- 取号 ----

    async def _run_obtain_shop(
        self, record: PreviewRecord, plan: ShopPlan, counter: _Counter
    ) -> None:
        async def job(client: FxgClient) -> None:
            await self._obtain_batch(client, record, plan, counter)

        await self._runner.run(plan.shop_id, job, actor=record.actor)

    async def _obtain_batch(
        self, client: FxgClient, record: PreviewRecord, plan: ShopPlan, counter: _Counter
    ) -> None:
        rows, items = self._reload(plan.order_ids)
        active = self._active_waybills([r["id"] for r in rows])
        attempts: list[tuple[dict, dict, int]] = []
        for row in rows:
            reasons = order_blockers(
                row["platform_status"], row["combine_id"], items[row["id"]],
                row["id"] in active, row["status"])
            if reasons:
                counter.skipped += 1
                self._publish(record, row, "skipped", reason="；".join(reasons))
                continue
            outcome, task, seq = self._prepare_task(row, record.mode, record.actor)
            if outcome == "done":
                counter.ok += 1
                tracking = (active.get(row["id"]) or {}).get("waybill_no")
                self._publish(record, row, "success", tracking_no=tracking)
            elif outcome == "busy":
                counter.skipped += 1
                self._publish(record, row, "skipped", reason="同一订单的取号正在执行")
            else:
                attempts.append((row, task, seq))
        if not attempts:
            return
        merged = [{**row, "items": items[row["id"]]} for row, _, _ in attempts]
        order_list = order_list_payload(merged)
        exp_type = await self._exp_type(client, plan, [r["id"] for r, _, _ in attempts])
        if exp_type is None:
            for row, task, _ in attempts:
                self._finish_failed(record, row, task, counter, "查询产品类型失败")
            return
        try:
            if record.mode == MODE_FETCH_AND_SHIP:
                body = fetch_and_ship_body(
                    courier_code=plan.courier_code, template_code=plan.template_code,
                    address=plan.address, exp_type=exp_type, ebill_id=plan.ebill_id,
                    net_code=plan.net_code, order_list=order_list, printer=self._printer,
                )
                resp = await client.call(ep.LABEL_FETCH_AND_SHIP, body=body)
                result = parse_fetch_and_ship_result(resp)
            else:
                body = obtain_body(
                    courier_code=plan.courier_code, template_code=plan.template_code,
                    address=plan.address, exp_type=exp_type, ebill_id=plan.ebill_id,
                    net_code=plan.net_code, order_list=order_list, printer=self._printer,
                )
                resp = await client.call(ep.LABEL_FETCH, body=body)
                result = parse_fetch_result(resp)
        except TransientError:
            await self._recover(client, record, attempts, counter, "取号响应超时")
            return
        except BizRejected as e:
            for row, task, _ in attempts:
                self._finish_failed(record, row, task, counter, str(e))
            return
        await self._apply_result(client, record, plan, attempts, result, counter)

    async def _apply_result(
        self, client: FxgClient, record: PreviewRecord, plan: ShopPlan,
        attempts: list[tuple[dict, dict, int]], result, counter: _Counter,
    ) -> None:
        by_order = {no: s for s in result.success for no in s.order_nos}
        failed: dict[str, str] = {}
        unref: list[str] = []
        for f in result.failures:
            if f.order_nos:
                for no in f.order_nos:
                    failed[no] = f.fail_msg
            else:
                unref.append(f.fail_msg)
        needs_recovery: list[tuple[dict, dict, int]] = []
        done: set[str] = set()
        for row, task, seq in attempts:
            no = row["order_no"]
            if no in by_order:
                self._record_success(record, plan, row, task, seq, by_order[no], counter)
                done.add(no)
                continue
            msg = failed.get(no) or (unref[0] if unref else PARTIAL_RESULT_REASON)
            done.add(no)
            if LABEL_NOT_FOUND_MSG in msg:
                needs_recovery.append((row, task, seq))
            else:
                self._finish_failed(record, row, task, counter, msg)
        if needs_recovery:
            await self._recover(client, record, needs_recovery, counter, LABEL_NOT_FOUND_MSG)

    async def _recover(
        self, client: FxgClient, record: PreviewRecord,
        attempts: list[tuple[dict, dict, int]], counter: _Counter, reason: str,
    ) -> None:
        """结果不明：查回运单号；查到补写面单，查不到保持待核实（backend 5.12）。"""
        for row, task, seq in attempts:
            tracking: str | None = None
            try:
                tracking = await find_tracking_no(client, row["order_no"])
            except (TransientError, BizRejected, ParseError):
                tracking = None
            if tracking:
                plan = self._plan_of(record, row["shop_id"])
                success = FetchSuccess(
                    (row["order_no"],), plan.courier_code, tracking, plan.template_code,
                    None, None)
                self._record_success(record, plan, row, task, seq, success, counter)
            else:
                self._finish_verifying(record, row, task, counter, reason)

    # ---- 作废 ----

    async def _run_void_shop(
        self, record: PreviewRecord, plan: VoidPlan, counter: _Counter
    ) -> None:
        async def job(client: FxgClient) -> None:
            with self._engine.connect() as conn:
                waybills = waybill_store.by_ids(conn, plan.waybill_ids)
                orders = {r["id"]: r for r in order_store.get_by_ids(
                    conn, [w["order_id"] for w in waybills])}
            attempts = []
            for w in waybills:
                order = orders.get(w["order_id"])
                if order is None or w["status"] not in ("active", "printed") \
                        or order["status"] not in VOIDABLE_STATUSES:
                    counter.skipped += 1
                    self._publish(record, order or {"order_no": str(w["order_id"])},
                                  "skipped", reason="面单或订单状态已变化")
                    continue
                key = void_key(w["shop_id"], w["courier_code"], w["waybill_no"])
                outcome, task = self._prepare_void_task(w, order, key, record.actor)
                if outcome == "done":
                    counter.ok += 1
                    self._publish(record, order, "success", tracking_no=w["waybill_no"])
                elif outcome == "busy":
                    counter.skipped += 1
                    self._publish(record, order, "skipped", reason="同一面单的作废正在执行")
                else:
                    attempts.append((w, order, task))
            if not attempts:
                return
            body = cancel_body([w for w, _, _ in attempts])
            try:
                resp = await client.call(ep.CANCEL_TRACKING_NOS, body=body)
            except (TransientError, BizRejected) as e:
                for _w, order, task in attempts:
                    self._finish_failed(record, order, task, counter,
                                        VOID_UNKNOWN_REASON if isinstance(e, TransientError)
                                        else str(e))
                return
            result = parse_cancel_result(resp)
            ok_tracking = {s.tracking_no for s in result.success}
            fail_msg = {f.tracking_no: f.fail_msg for f in result.failures if f.tracking_no}
            for w, order, task in attempts:
                if w["waybill_no"] in ok_tracking:
                    self._record_void(order, task, w, counter, record)
                else:
                    msg = (fail_msg.get(w["waybill_no"]) or result.fail_msg
                           or "平台未返回该面单的作废结果")
                    self._finish_failed(record, order, task, counter, msg)

        await self._runner.run(plan.shop_id, job, actor=record.actor)

    # ---- 状态写入 ----

    def _record_success(
        self, record: PreviewRecord, plan: ShopPlan, row: dict, task: dict, seq: int,
        success: FetchSuccess, counter: _Counter,
    ) -> None:
        now = self._now()
        target = (LocalOrderStatus.SHIPPED if record.mode == MODE_FETCH_AND_SHIP
                  else LocalOrderStatus.LABEL_OBTAINED)
        try:
            with self._engine.begin() as conn:
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
                        exp_type=None, ebill_id=plan.ebill_id, net_code=plan.net_code,
                        status="active", now=now,
                    )
                order_store.set_local_status(
                    conn, row["shop_id"], row["order_no"], target, now)
                task_store.finish(conn, task["id"], TaskStatus.SUCCESS, None, now)
        except sa.exc.IntegrityError:
            # 运单号或有效面单冲突：多为另一个执行已写入，复用现有面单
            with self._engine.begin() as conn:
                active = waybill_store.active_by_orders(conn, [row["id"]]).get(row["id"])
                if active is None:
                    task_store.finish(
                        conn, task["id"], TaskStatus.FAILED, "运单号已存在，无法写入", now)
                    counter.failed += 1
                    self._publish(record, row, "failed", reason="运单号已存在，无法写入")
                    return
                order_store.set_local_status(
                    conn, row["shop_id"], row["order_no"], target, now)
                task_store.finish(conn, task["id"], TaskStatus.SUCCESS, None, now)
            counter.ok += 1
            self._publish(record, row, "success", tracking_no=active["waybill_no"])
            return
        counter.ok += 1
        self._publish(record, row, "success", tracking_no=success.tracking_no)

    def _record_void(self, order: dict, task: dict, waybill: dict, counter: _Counter,
                     record: PreviewRecord) -> None:
        now = self._now()
        with self._engine.begin() as conn:
            waybill_store.mark_void(conn, waybill["id"], now)
            order_store.set_local_status(
                conn, order["shop_id"], order["order_no"], LocalOrderStatus.PENDING_LABEL, now)
            task_store.finish(conn, task["id"], TaskStatus.SUCCESS, None, now)
        counter.ok += 1
        self._publish(record, order, "success", tracking_no=waybill["waybill_no"])

    def _finish_failed(self, record: PreviewRecord, row: dict, task: dict,
                       counter: _Counter, reason: str) -> None:
        now = self._now()
        with self._engine.begin() as conn:
            task_store.finish(conn, task["id"], TaskStatus.FAILED, reason, now)
            current = conn.execute(sa.select(order_store.orders.c.status).where(
                order_store.orders.c.id == row["id"])).scalar()
            if current in (LocalOrderStatus.SYNCED.value, LocalOrderStatus.PENDING_LABEL.value):
                order_store.mark_exception(conn, row["shop_id"], row["order_no"], reason, now)
        counter.failed += 1
        self._publish(record, row, "failed", reason=reason)

    def _finish_verifying(self, record: PreviewRecord, row: dict, task: dict,
                          counter: _Counter, reason: str) -> None:
        now = self._now()
        with self._engine.begin() as conn:
            task_store.finish(conn, task["id"], TaskStatus.VERIFYING, reason, now)
        counter.verifying += 1
        self._publish(record, row, "verifying", reason=RECOVERY_MISS_REASON)

    # ---- 任务与参数 ----

    def _prepare_task(self, row: dict, mode: str, actor: str) -> tuple[str, dict, int]:
        now = self._now()
        with self._engine.begin() as conn:
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

    def _prepare_void_task(self, waybill: dict, order: dict, key: str,
                           actor: str) -> tuple[str, dict]:
        now = self._now()
        with self._engine.begin() as conn:
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

    async def _exp_type(
        self, client: FxgClient, plan: ShopPlan, order_ids: list[int]
    ) -> str | None:
        try:
            resp = await client.call(ep.PRODUCT_TYPES, body={
                "logistics_company_code": plan.courier_code,
                "shop_order_ids": [str(i) for i in order_ids],
            })
        except (TransientError, BizRejected, ParseError):
            return None
        return parse_product_types(resp).exp_type or DEFAULT_EXP_TYPE

    # ---- 读库辅助 ----

    def _reload(self, order_ids) -> tuple[list[dict], dict]:
        with self._engine.connect() as conn:
            rows = order_store.get_by_ids(conn, list(order_ids))
            items = order_store.items_by_order(conn, [r["id"] for r in rows])
        return rows, items

    def _active_waybills(self, order_ids) -> dict[int, dict]:
        with self._engine.connect() as conn:
            return waybill_store.active_by_orders(conn, order_ids)

    def _order_ids_for_waybills(self, waybill_ids) -> list[int]:
        with self._engine.connect() as conn:
            return [w["order_id"] for w in waybill_store.by_ids(conn, list(waybill_ids))]

    @staticmethod
    def _plan_of(record: PreviewRecord, shop_id: int) -> ShopPlan:
        return next(p for p in record.shops if p.shop_id == shop_id)

    def _now(self) -> str:
        return self._clock().strftime(_ISO_FMT)

    def _publish(self, record: PreviewRecord, row: dict, result: str,
                 tracking_no: str | None = None, reason: str | None = None) -> None:
        self._events.publish(LABEL_PROGRESS, {
            "preview_id": record.preview_id, "mode": record.mode,
            "shop_id": row.get("shop_id"), "order_id": row.get("id"),
            "order_no": row.get("order_no"), "result": result,
            "tracking_no": tracking_no, "reason": reason,
        })
