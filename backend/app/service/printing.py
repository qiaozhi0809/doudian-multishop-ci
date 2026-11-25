"""M3 打印编排（flows 7.4 / 10）：官方组件直连（P1）+ 无打印数据转手动补打（P3）。

- 打印前按运单号批量取补打数据（batchGetPrintInfos）：补齐 templateURL / OAuth，
  并给「物流查询恢复的面单」（print_data 为空）补上打印数据，取到即落库；
- 组件回执失败重试一次（MAX_ATTEMPTS）；仍失败记 print_job(failed) 并提示手动补打；
- 每次提交一张面单一条 print_job（attempts 记组件尝试次数），所有失败可追溯；
- 不自动降级到自渲染 PDF（flows 7.4）：没有打印数据时只提示手动补打。
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.print_parsers import parse_print_infos
from app.adapter.doudian.print_request import print_infos_body
from app.adapter.print.component import PrintComponent, PrinterProbe
from app.adapter.print.protocol import DocumentSpec, PrintOutcome
from app.domain.errors import DryRunBlocked, InvalidRequest, NotFound
from app.domain.models import PrintInfo
from app.domain.order_status import LocalOrderStatus
from app.domain.print_status import RESULT_NO_PRINT_DATA, PrintJobStatus
from app.service.background import TaskAlreadyRunning, TaskRegistry
from app.service.events import PRINT_DONE, PRINT_PROGRESS, EventBus
from app.service.shop_runner import ShopRunner
from app.store import order_store, print_job_store, waybill_store

log = structlog.get_logger()

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
MANUAL_HINT = "请到抖店后台手动补打面单"
NO_PRINT_DATA_DETAIL = "该面单没有打印数据（多为物流查询恢复的面单），无法本地打印"
COMPONENT_MISSING = "打印组件未启动或没有默认打印机，请先启动抖店官方打印组件"
PRINTABLE_STATUSES = ("active", "printed")
MAX_ATTEMPTS = 2  # flows 10：失败重试一次后转 P3 手动补打
_TASK_NAME = "print-jobs"


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class PrintStarted:
    job_ids: list[int]
    waybill_ids: list[int]


@dataclass(frozen=True)
class PrintSummary:
    ok: int = 0
    failed: int = 0
    manual: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class _Target:
    waybill_id: int
    waybill_no: str
    shop_id: int
    order_id: int
    order_no: str
    print_data: str | None
    sign: str | None


class PrintingService:
    def __init__(
        self, engine: Engine, runner: ShopRunner, component: PrintComponent,
        events: EventBus | None = None, *, dry_run: bool = False,
        default_printer: str = "", tasks: TaskRegistry | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._engine = engine
        self._runner = runner
        self._component = component
        self._events = events or EventBus()
        self._dry_run = dry_run
        self._default_printer = default_printer
        self._tasks = tasks or TaskRegistry()
        self._clock = clock

    # ---- 组件状态 ----

    async def status(self) -> dict:
        probe = await self._component.probe()
        return _probe_view(probe, self._now())

    def job(self, job_id: int) -> dict:
        with self._engine.connect() as conn:
            row = print_job_store.get(conn, job_id)
        if row is None:
            raise NotFound(f"打印任务不存在: {job_id}")
        return row

    def waybill_views(self, waybill_ids: Sequence[int]) -> list[dict]:
        """每张面单的可打印信息与最近一次打印任务（界面状态展示用）。"""
        ids = list(dict.fromkeys(int(i) for i in waybill_ids))
        if not ids:
            return []
        with self._engine.connect() as conn:
            waybills = print_job_store.with_waybill_no(conn, ids)
            jobs = print_job_store.latest_by_waybills(conn, ids)
        out: list[dict] = []
        for wid in ids:
            waybill = waybills.get(wid)
            if waybill is None:
                continue
            out.append({
                "waybill_id": wid,
                "waybill_no": waybill["waybill_no"],
                "waybill_status": waybill["status"],
                "has_print_data": waybill["print_data"] is not None,
                "job": jobs.get(wid),
            })
        return out

    # ---- 入口 ----

    async def submit(
        self, waybill_ids: Sequence[int], actor: str, printer_name: str | None = None
    ) -> PrintStarted:
        # 打印机是本机资源：同一时刻只跑一个批次，避免多店同时打单抢占（flows 10）
        if self._tasks.is_running(_TASK_NAME):
            raise TaskAlreadyRunning("已有打印任务进行中，请稍候")
        targets = self._load(waybill_ids)
        printer = await self._resolve_printer(printer_name)
        jobs = self._create_jobs(targets, printer)
        self._tasks.spawn(_TASK_NAME, self._run(jobs, targets, printer, actor))
        return PrintStarted(
            [job_id for job_id, _ in jobs], [t.waybill_id for t in targets])

    async def run_inline(
        self, waybill_ids: Sequence[int], actor: str, printer_name: str | None = None
    ) -> PrintSummary:
        targets = self._load(waybill_ids)
        printer = await self._resolve_printer(printer_name)
        jobs = self._create_jobs(targets, printer)
        return await self._run(jobs, targets, printer, actor)

    # ---- 读取与校验 ----

    def _load(self, waybill_ids: Sequence[int]) -> list[_Target]:
        if self._dry_run:
            raise DryRunBlocked("演练模式下不能打印面单")
        unique = list(dict.fromkeys(int(i) for i in waybill_ids))
        if not unique:
            raise InvalidRequest("请选择要打印的面单")
        with self._engine.connect() as conn:
            rows = {r["id"]: r for r in waybill_store.by_ids(conn, unique)}
            missing = [i for i in unique if i not in rows]
            if missing:
                raise NotFound(f"面单不存在: {missing[0]}")
            order_ids = [rows[i]["order_id"] for i in unique]
            orders = {o["id"]: o for o in order_store.get_by_ids(conn, order_ids)}
        targets: list[_Target] = []
        for wid in unique:
            row = rows[wid]
            if row["status"] not in PRINTABLE_STATUSES:
                raise InvalidRequest(f"面单 {row['waybill_no'] or wid} 已作废，不能打印")
            order = orders.get(row["order_id"])
            if order is None or not row["waybill_no"]:
                raise NotFound(f"面单 {wid} 缺少订单或运单号")
            targets.append(_Target(
                waybill_id=wid, waybill_no=row["waybill_no"], shop_id=row["shop_id"],
                order_id=order["id"], order_no=order["order_no"],
                print_data=row["print_data"], sign=row["sign"],
            ))
        return targets

    async def _resolve_printer(self, printer_name: str | None) -> str:
        if printer_name and printer_name.strip():
            return printer_name.strip()
        if self._default_printer:
            return self._default_printer
        probe = await self._component.probe()
        if not probe.available or not probe.default_printer:
            raise InvalidRequest(COMPONENT_MISSING)
        return probe.default_printer

    def _create_jobs(
        self, targets: list[_Target], printer: str
    ) -> list[tuple[int, _Target]]:
        now = self._now()
        with self._engine.begin() as conn:
            return [
                (print_job_store.insert(
                    conn, waybill_id=t.waybill_id, printer_name=printer, now=now), t)
                for t in targets
            ]

    # ---- 执行 ----

    async def _run(
        self, jobs: list[tuple[int, _Target]], targets: list[_Target],
        printer: str, actor: str,
    ) -> PrintSummary:
        infos = await self._fetch_infos(targets, actor)
        self._backfill(targets, infos)
        ok = failed = manual = 0
        for job_id, target in jobs:
            spec = build_document(target, infos.get(target.waybill_no))
            if spec is None:
                self._finish_manual(job_id, target)
                manual += 1
                continue
            outcome = await self._attempt_print(job_id, printer, spec)
            if outcome.ok:
                self._finish_success(job_id, target)
                ok += 1
            else:
                self._finish_failed(job_id, target, outcome)
                failed += 1
        summary = PrintSummary(ok=ok, failed=failed, manual=manual, skipped=0)
        self._events.publish(PRINT_DONE, {
            "ok": ok, "failed": failed, "manual": manual, "skipped": 0})
        return summary

    async def _attempt_print(
        self, job_id: int, printer: str, spec: DocumentSpec
    ) -> PrintOutcome:
        outcome = PrintOutcome(False, "no_response", "未执行")
        for attempt in range(1, MAX_ATTEMPTS + 1):
            with self._engine.begin() as conn:
                print_job_store.bump_attempts(conn, job_id, attempt)
            outcome = await self._component.print_documents(printer, [spec])
            if outcome.ok:
                break
        return outcome

    async def _fetch_infos(
        self, targets: list[_Target], actor: str
    ) -> dict[str, PrintInfo]:
        """补打数据按店批量取；失败只降级（用本地 print_data），不阻塞打印。"""
        by_shop: dict[int, list[str]] = {}
        for target in targets:
            by_shop.setdefault(target.shop_id, []).append(target.waybill_no)
        merged: dict[str, PrintInfo] = {}
        for shop_id, tracking_nos in by_shop.items():
            try:
                merged.update(
                    await self._runner.run(shop_id, _call_infos(tracking_nos), actor=actor))
            except Exception as e:  # 组件打印不依赖补打接口：失败就用本地数据
                log.warning(
                    "printing.print_infos_failed", shop_id=shop_id,
                    error=type(e).__name__)
        return merged

    def _backfill(self, targets: list[_Target], infos: dict[str, PrintInfo]) -> None:
        pending = [
            (t, infos[t.waybill_no]) for t in targets
            if not t.print_data and infos.get(t.waybill_no)
            and infos[t.waybill_no].print_data
        ]
        if not pending:
            return
        with self._engine.begin() as conn:
            for target, info in pending:
                waybill_store.set_print_data(
                    conn, target.waybill_id, info.print_data, info.sign or target.sign)

    # ---- 结果写入 ----

    def _finish_success(self, job_id: int, target: _Target) -> None:
        now = self._now()
        with self._engine.begin() as conn:
            print_job_store.finish(conn, job_id, PrintJobStatus.SUCCESS, "success", None, now)
            waybill_store.mark_printed(conn, target.waybill_id, now)
            order = order_store.get_by_ids(conn, [target.order_id])[0]
            if order["status"] == LocalOrderStatus.LABEL_OBTAINED.value:
                order_store.set_local_status(
                    conn, target.shop_id, target.order_no,
                    LocalOrderStatus.PRINTED, now)
        self._publish(job_id, target, "success", None)

    def _finish_manual(self, job_id: int, target: _Target) -> None:
        detail = f"{NO_PRINT_DATA_DETAIL}；{MANUAL_HINT}"
        with self._engine.begin() as conn:
            print_job_store.finish(
                conn, job_id, PrintJobStatus.FAILED, RESULT_NO_PRINT_DATA, detail, self._now())
        self._publish(job_id, target, "manual", detail)

    def _finish_failed(self, job_id: int, target: _Target, outcome: PrintOutcome) -> None:
        detail = f"{outcome.detail}；{MANUAL_HINT}" if outcome.detail else MANUAL_HINT
        with self._engine.begin() as conn:
            print_job_store.finish(
                conn, job_id, PrintJobStatus.FAILED, outcome.code, detail, self._now())
        self._publish(job_id, target, "failed", detail)

    def _publish(
        self, job_id: int, target: _Target, result: str, detail: str | None
    ) -> None:
        self._events.publish(PRINT_PROGRESS, {
            "job_id": job_id, "waybill_id": target.waybill_id,
            "order_no": target.order_no, "result": result, "detail": detail,
        })

    def _now(self) -> str:
        return self._clock().strftime(ISO_FMT)


def _call_infos(tracking_nos: Sequence[str]):
    async def job(client: FxgClient) -> dict[str, PrintInfo]:
        resp = await client.call(
            ep.BATCH_GET_PRINT_INFOS, body=print_infos_body(tracking_nos))
        return parse_print_infos(resp)

    return job


def build_document(target, info: PrintInfo | None) -> DocumentSpec | None:
    """合并补打数据与本地面单；没有任何打印数据时返回 None（转手动补打）。"""
    print_data = (info.print_data if info and info.print_data else target.print_data)
    if not print_data:
        return None
    return DocumentSpec(
        waybill_no=target.waybill_no,
        print_data=print_data,
        sign=info.sign if info and info.sign else target.sign,
        template_url=info.template_url if info else None,
        params=info.params if info else None,
        custom_print_data=info.custom_print_data if info else None,
        custom_template_url=info.custom_template_url if info else None,
    )


def _probe_view(probe: PrinterProbe, checked_at: str) -> dict:
    return {
        "available": probe.available,
        "printers": list(probe.printers),
        "default_printer": probe.default_printer,
        "error": probe.error,
        "checked_at": checked_at,
    }
