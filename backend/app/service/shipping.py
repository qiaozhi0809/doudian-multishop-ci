"""M4 发货（backend 5.6 / flows 7.5）：发货前检查 → 按运单号批量发货。

- 检查：每店 `sendcheck`（带店铺默认发货地址）；有二次确认项时整批拦截，
  前端确认后带 `double_check_ack` 重新提交。
- 幂等：`tasks.idempotency_key = ship:{shop_id}:{courier_code}:{tracking_no}`。
  平台不阻止重复发货（write.md A.2.4），本地必须先查键；`shipment` 的
  success 唯一索引是数据库兜底。
- 失败：整批瞬时错误退避重试 3 次；仍失败逐店 / 逐包裹标记失败，订单状态不动，可重试。
- 写操作：演练模式拒绝；每批写审计（逐次 HTTP 调用另由 ShopRunner 审计）。
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import structlog
from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.errors import BizRejected, EgressUnavailable, TransientError
from app.adapter.doudian.shipping_parsers import parse_deliver_result
from app.adapter.doudian.shipping_request import deliver_body
from app.domain.audit import CallRecord
from app.domain.errors import DryRunBlocked, InvalidRequest
from app.domain.idempotency import ship_key
from app.domain.models import DeliverResult, SendCheckResult
from app.domain.task_status import TaskStatus, TaskType
from app.service.background import TaskAlreadyRunning, TaskRegistry
from app.service.events import SHIP_DONE, SHIP_PROGRESS, EventBus
from app.service.shipping_plan import (
    BlockedShip,
    PackageGroup,
    ShipTarget,
    call_sendcheck,
    default_address,
    describe,
    group_packages,
    load_targets,
    pool_view,
)
from app.service.shop_runner import ShopRunner
from app.store import audit_store, shipping_store, task_store

log = structlog.get_logger()

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
DELIVER_ATTEMPTS = 3
RETRY_DELAYS_S = (1, 2)
NO_RESULT_REASON = "平台未返回该包裹的发货结果"
UNKNOWN_RESULT_REASON = "发货结果不明（重试后仍失败），可人工核对后重试"
ALREADY_SHIPPED_REASON = "已发货（幂等跳过）"
BUSY_REASON = "同一运单号正在发货"
_TASK_NAME = "shipping"


def utc_now() -> datetime:
    return datetime.now(UTC)


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


@dataclass(frozen=True)
class ShipSummary:
    ok: int = 0
    failed: int = 0
    skipped: int = 0


@dataclass
class _Counter:
    ok: int = 0
    failed: int = 0
    skipped: int = 0

    def summary(self) -> ShipSummary:
        return ShipSummary(self.ok, self.failed, self.skipped)


class ShippingService:
    def __init__(
        self, engine: Engine, runner: ShopRunner, events: EventBus | None = None, *,
        dry_run: bool = False, tasks: TaskRegistry | None = None,
        clock: Callable[[], datetime] = utc_now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._engine = engine
        self._runner = runner
        self._events = events or EventBus()
        self._dry_run = dry_run
        self._tasks = tasks or TaskRegistry()
        self._clock = clock
        self._sleep = sleep
        self._busy = False

    # ---- 队列视图 ----

    def pool(
        self, shop_ids: Sequence[int] | None, page: int, page_size: int,
    ) -> tuple[list[dict], int]:
        return pool_view(self._engine, shop_ids, page, page_size)

    def batch(self, batch_id: str) -> list[dict]:
        with self._engine.connect() as conn:
            return shipping_store.by_batch(conn, batch_id)

    # ---- 发货前检查 ----

    async def check(self, order_ids: Sequence[int], actor: str) -> CheckView:
        targets, blocked = load_targets(self._engine, order_ids)
        if not targets and not blocked:
            raise InvalidRequest("没有可发货的订单")
        names = {t.shop_id: t.shop_name for t in targets}
        shops: list[ShopCheck] = []
        errors: list[ShopCheckError] = []
        for shop_id in sorted({t.shop_id for t in targets}):
            group = [t for t in targets if t.shop_id == shop_id]
            address = default_address(self._engine, shop_id)
            if address is None:
                errors.append(ShopCheckError(shop_id, names[shop_id], "没有默认发货地址"))
                continue
            order_nos = tuple(t.order_no for t in group)
            try:
                result = await self._runner.run(
                    shop_id, call_sendcheck(order_nos, address), actor=actor)
            except Exception as e:  # 单店失败隔离：其余店照常检查
                log.warning("shipping.check_failed", shop_id=shop_id, error=type(e).__name__)
                errors.append(ShopCheckError(shop_id, names[shop_id], describe(e)))
                continue
            shops.append(ShopCheck(shop_id, names[shop_id], order_nos, result))
        return CheckView(tuple(shops), tuple(blocked), tuple(errors), tuple(targets))

    # ---- 提交发货 ----

    async def ship(
        self, order_ids: Sequence[int], actor: str, double_check_ack: bool = False,
    ) -> ShipStarted:
        if self._dry_run:
            raise DryRunBlocked("演练模式下不能执行发货")
        if self._busy or self._tasks.is_running(_TASK_NAME):
            raise TaskAlreadyRunning("已有发货批次进行中，请稍候")
        self._busy = True  # 同步占位：检查是网络请求，期间不许第二个批次进入
        try:
            view = await self.check(order_ids, actor)
            if not view.targets:
                raise InvalidRequest("没有可发货的订单")
            if view.double_check_total and not double_check_ack:
                raise InvalidRequest(
                    f"发货前检查有 {view.double_check_total} 个二次确认项，请确认后再提交")
            packages = group_packages(view.targets)
            batch_id = uuid4().hex
            now = self._now()
            with self._engine.begin() as conn:
                shipping_store.insert_pending(conn, [
                    {"shop_id": p.shop_id, "order_id": t.order_id,
                     "waybill_id": t.waybill_id, "courier_code": p.courier_code,
                     "tracking_no": p.tracking_no}
                    for p in packages for t in p.targets
                ], batch_id, now)
                audit_store.insert(conn, CallRecord(
                    shop_id=None, action="ship_batch", actor=actor,
                    req_summary={"orders": len(view.targets), "packages": len(packages)},
                    resp_summary={"batch_id": batch_id, "status": "started"},
                    result="started",
                ), now)
            self._tasks.spawn(_TASK_NAME, self._run(batch_id, view, packages, actor))
        except Exception:
            self._busy = False
            raise
        return ShipStarted(
            batch_id, sorted({t.shop_id for t in view.targets}), len(packages),
            len(view.targets))

    # ---- 执行 ----

    async def _run(
        self, batch_id: str, view: CheckView, packages: list[PackageGroup], actor: str,
    ) -> ShipSummary:
        counter = _Counter()
        try:
            errors = {e.shop_id: e.reason for e in view.shop_errors}
            for shop_id in sorted({p.shop_id for p in packages}):
                shop_packages = [p for p in packages if p.shop_id == shop_id]
                if shop_id in errors:
                    self._fail_all(batch_id, shop_packages, errors[shop_id], counter, None)
                    continue

                async def job(client: FxgClient, _pkgs=shop_packages) -> None:
                    await self._deliver_shop(client, batch_id, _pkgs, counter, actor)

                try:
                    await self._runner.run(shop_id, job, actor=actor)
                except Exception as e:  # 预检失败等：整店标记失败，不影响其他店
                    log.warning(
                        "shipping.shop_failed", shop_id=shop_id, error=type(e).__name__)
                    self._fail_all(batch_id, shop_packages, describe(e), counter, None)
        finally:
            self._busy = False
        summary = counter.summary()
        self._events.publish(SHIP_DONE, {"batch_id": batch_id, **vars(summary)})
        now = self._now()
        with self._engine.begin() as conn:
            audit_store.insert(conn, CallRecord(
                shop_id=None, action="ship_batch", actor=actor,
                req_summary={"batch_id": batch_id},
                resp_summary=vars(summary), result="ok",
            ), now)
        return summary

    async def _deliver_shop(
        self, client: FxgClient, batch_id: str, packages: list[PackageGroup],
        counter: _Counter, actor: str,
    ) -> None:
        ready: list[tuple[PackageGroup, Mapping]] = []
        for package in packages:
            outcome, task = self._prepare(batch_id, package, actor)
            if outcome == "done":
                self._finish_done(batch_id, package, counter)
            elif outcome == "busy":
                self._fail_all(batch_id, [package], BUSY_REASON, counter, None)
            elif task is not None:
                ready.append((package, task))
        if not ready:
            return
        body = deliver_body([
            {"courier_code": p.courier_code, "tracking_no": p.tracking_no}
            for p, _ in ready
        ])
        try:
            resp = await self._deliver(client, body)
        except BizRejected as e:
            self._fail_all(batch_id, [p for p, _ in ready], str(e), counter,
                           [t for _, t in ready])
            return
        except TransientError:
            self._fail_all(batch_id, [p for p, _ in ready], UNKNOWN_RESULT_REASON,
                           counter, [t for _, t in ready])
            return
        self._apply_result(batch_id, ready, parse_deliver_result(resp), counter)

    async def _deliver(self, client: FxgClient, body: dict) -> dict:
        last: Exception | None = None
        for attempt in range(DELIVER_ATTEMPTS):
            if attempt:
                await self._sleep(RETRY_DELAYS_S[attempt - 1])
            try:
                return await client.call(ep.BATCH_DELIVER, body=body)
            except EgressUnavailable:  # 出口异常即停：不重试、不改走直连（backend 5.17）
                raise
            except TransientError as e:  # 平台不拦重复发货：重试是安全的（A.2.4）
                last = e
        assert last is not None
        raise last

    def _apply_result(
        self, batch_id: str, ready: list[tuple[PackageGroup, Mapping]],
        result: DeliverResult, counter: _Counter,
    ) -> None:
        ok_tracking = {s.tracking_no for s in result.success}
        fail_msgs = {f.tracking_no: f.fail_msg for f in result.failures if f.tracking_no}
        unref = [f.fail_msg for f in result.failures if not f.tracking_no]
        for package, task in ready:
            if package.tracking_no in ok_tracking:
                self._finish_success(batch_id, package, task, counter)
            else:
                msg = (fail_msgs.get(package.tracking_no)
                       or (unref[0] if unref else NO_RESULT_REASON))
                self._fail_all(batch_id, [package], msg, counter, [task])

    # ---- 幂等与状态写入 ----

    def _prepare(
        self, batch_id: str, package: PackageGroup, actor: str,
    ) -> tuple[str, Mapping | None]:
        now = self._now()
        order_ids = [t.order_id for t in package.targets]
        with self._engine.begin() as conn:
            if shipping_store.already_shipped_orders(conn, package.shop_id, order_ids):
                return "done", None
            key = ship_key(package.shop_id, package.courier_code, package.tracking_no)
            existing = task_store.get_by_key(conn, key)
            if existing and existing["status"] in (
                TaskStatus.RUNNING.value, TaskStatus.QUEUED.value
            ):
                return "busy", existing
            task = task_store.start(
                conn, key=key, shop_id=package.shop_id, type=TaskType.SHIP.value,
                payload={"batch_id": batch_id, "order_ids": order_ids,
                         "tracking_no": package.tracking_no},
                actor=actor, now=now,
            )
        if task["status"] == TaskStatus.SUCCESS.value:
            return "done", task
        return "started", task

    def _finish_done(
        self, batch_id: str, package: PackageGroup, counter: _Counter,
    ) -> None:
        self._write_success(batch_id, package, None)
        for target in package.targets:
            counter.skipped += 1
            self._publish(batch_id, target, "skipped", ALREADY_SHIPPED_REASON)

    def _finish_success(
        self, batch_id: str, package: PackageGroup, task: Mapping, counter: _Counter,
    ) -> None:
        self._write_success(batch_id, package, task)
        for target in package.targets:
            counter.ok += 1
            self._publish(batch_id, target, "success", None)

    def _write_success(
        self, batch_id: str, package: PackageGroup, task: Mapping | None,
    ) -> None:
        now = self._now()
        with self._engine.begin() as conn:
            shipping_store.mark_orders_shipped(
                conn, package.shop_id, [t.order_id for t in package.targets], now)
            for target in package.targets:
                shipping_store.finish_order(
                    conn, batch_id, target.order_id, "success", None, now)
            if task is not None:
                task_store.finish(conn, task["id"], TaskStatus.SUCCESS, None, now)

    def _fail_all(
        self, batch_id: str, packages: list[PackageGroup], reason: str,
        counter: _Counter, tasks: list[Mapping] | None,
    ) -> None:
        now = self._now()
        with self._engine.begin() as conn:
            for package in packages:
                for target in package.targets:
                    shipping_store.finish_order(
                        conn, batch_id, target.order_id, "failed", reason, now)
            for task in tasks or []:
                task_store.finish(conn, task["id"], TaskStatus.FAILED, reason, now)
        for package in packages:
            for target in package.targets:
                counter.failed += 1
                self._publish(batch_id, target, "failed", reason)

    # ---- 其它 ----

    def _publish(
        self, batch_id: str, target: ShipTarget, result: str, reason: str | None,
    ) -> None:
        self._events.publish(SHIP_PROGRESS, {
            "batch_id": batch_id, "shop_id": target.shop_id, "order_id": target.order_id,
            "order_no": target.order_no, "result": result,
            "tracking_no": target.tracking_no, "reason": reason,
        })

    def _now(self) -> str:
        return self._clock().strftime(ISO_FMT)
