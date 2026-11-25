"""M4 跨店对账（backend 5.8 / flows 7.6 / docs/api/reconcile.md）。

- 数据源：`searchlist` 的 `tab=all` 全状态订单，按 create_time / pay_time 落在窗口内过滤（G.5）。
- 快照：`order_fact`（G.7，替代原 orders_snapshot）；同一事务内先读旧快照 → 判定 →
  统一 upsert，保证比较基准是本次同步之前的快照（G.4）。
- 三类异常（G.3），每单最多一类。首次运行快照为空，所有已发货订单会报
  `platform_shipped_local_not`——这是建立基线的正常行为（G.6）。
- 批次按 run_id 落库；单店失败隔离，不影响其他店。
"""

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import structlog
from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.reconcile_parsers import parse_order_facts
from app.domain.errors import InvalidRequest, NotFound
from app.domain.models import OrderFactDTO
from app.domain.reconcile_rules import (
    FINDING_KINDS,
    FINDING_TITLES,
    FactView,
    Finding,
    classify,
)
from app.service.background import TaskAlreadyRunning, TaskRegistry
from app.service.events import RECONCILE_DONE, EventBus
from app.service.shipping_plan import describe
from app.service.shop_runner import ShopRunner
from app.store import reconcile_store, shop_store

log = structlog.get_logger()

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 90
MAX_PAGES = 200
STATUS_OPEN = "open"
STATUS_HANDLED = "handled"
_TASK_NAME = "reconcile"


def utc_now() -> datetime:
    return datetime.now(UTC)


def _in_window(fact: OrderFactDTO, cutoff: str) -> bool:
    """create_time 或 pay_time 任一落在窗口内即纳入（G.5）；两者都没有时不纳入。"""
    stamps = [t for t in (fact.pay_time, fact.create_time) if t]
    return any(t >= cutoff for t in stamps)


class ReconcileService:
    def __init__(
        self, engine: Engine, runner: ShopRunner, events: EventBus | None = None, *,
        tasks: TaskRegistry | None = None, clock: Callable[[], datetime] = utc_now,
        max_pages: int = MAX_PAGES,
    ) -> None:
        self._engine = engine
        self._runner = runner
        self._events = events or EventBus()
        self._tasks = tasks or TaskRegistry()
        self._clock = clock
        self._max_pages = max_pages

    # ---- 入口 ----

    async def run(
        self, shop_ids: Sequence[int], actor: str, window_days: int | None = None,
    ) -> dict:
        window = DEFAULT_WINDOW_DAYS if window_days is None else int(window_days)
        if not 1 <= window <= MAX_WINDOW_DAYS:
            raise InvalidRequest(f"对账窗口必须在 1~{MAX_WINDOW_DAYS} 天之间")
        ids = list(dict.fromkeys(int(i) for i in shop_ids))
        if not ids:
            raise InvalidRequest("没有可对账的店铺")
        if self._tasks.is_running(_TASK_NAME):
            raise TaskAlreadyRunning("已有对账批次进行中，请稍候")
        run_id = uuid4().hex
        now = self._now()
        with self._engine.begin() as conn:
            reconcile_store.create_run(conn, run_id, ids, window, now)
        self._tasks.spawn(_TASK_NAME, self._run(run_id, ids, actor, window))
        return {
            "run_id": run_id, "status": "running", "shop_ids": ids,
            "window_days": window, "started_at": now,
        }

    async def _run(
        self, run_id: str, shop_ids: list[int], actor: str, window_days: int,
    ) -> None:
        scanned = findings = 0
        errors: list[str] = []
        for shop_id in shop_ids:
            try:
                shop_scanned, shop_findings = await self._runner.run(
                    shop_id, _shop_job(self, shop_id, run_id, window_days), actor=actor)
            except Exception as e:  # 单店失败隔离
                log.warning("reconcile.shop_failed", shop_id=shop_id, error=type(e).__name__)
                errors.append(f"店铺 {shop_id}: {describe(e)}")
                continue
            scanned += shop_scanned
            findings += shop_findings
        status = "failed" if errors and len(errors) == len(shop_ids) else "success"
        now = self._now()
        with self._engine.begin() as conn:
            reconcile_store.finish_run(
                conn, run_id, status, scanned, findings,
                "；".join(errors) or None, now,
            )
        self._events.publish(RECONCILE_DONE, {
            "run_id": run_id, "status": status, "scanned": scanned,
            "findings": findings, "errors": len(errors),
        })

    # ---- 单店：拉取 → 同事务比较与落库 ----

    async def _sync_shop(
        self, client: FxgClient, shop_id: int, run_id: str, window_days: int,
    ) -> tuple[int, int]:
        facts = await self._fetch(client, window_days)
        if not facts:
            return 0, 0
        now = self._now()
        with self._engine.begin() as conn:  # G.4：同一事务内先读旧快照再统一 upsert
            old = reconcile_store.read_facts(conn, shop_id, [f.order_no for f in facts])
            classified: list[tuple[str, Finding]] = []
            for fact in facts:
                previous = old.get(fact.order_no)
                view = FactView(
                    previous["platform_status"] if previous else None,
                    previous["tracking_no"] if previous else None,
                    previous["company_code"] if previous else None,
                )
                current = FactView(fact.platform_status, fact.tracking_no, fact.company_code)
                finding = classify(view, current)
                if finding is not None:
                    classified.append((fact.order_no, finding))
            reconcile_store.upsert_facts(conn, shop_id, facts, now)
            reconcile_store.insert_findings(conn, run_id, shop_id, classified, now)
        return len(facts), len(classified)

    async def _fetch(self, client: FxgClient, window_days: int) -> list[OrderFactDTO]:
        cutoff = (self._clock() - timedelta(days=window_days)).strftime(ISO_FMT)
        by_no: dict[str, OrderFactDTO] = {}
        for page in range(self._max_pages):
            resp = await client.call(ep.SEARCHLIST, params=ep.searchlist_all_params(page))
            batch = parse_order_facts(resp)
            for fact in batch:
                if _in_window(fact, cutoff):
                    by_no[fact.order_no] = fact
            if len(batch) < ep.SEARCHLIST_MAX_PAGE_SIZE:
                break
        return list(by_no.values())

    # ---- 查询与处理 ----

    def findings(
        self, shop_ids: Sequence[int] | None, run_id: str | None, kind: str | None,
        status: str | None, page: int, page_size: int,
    ) -> tuple[list[dict], int, dict | None]:
        if kind is not None and kind not in FINDING_KINDS:
            raise InvalidRequest(f"不支持的对账异常类型: {kind}")
        if status is not None and status not in (STATUS_OPEN, STATUS_HANDLED):
            raise InvalidRequest(f"不支持的处理状态: {status}")
        with self._engine.connect() as conn:
            is_latest = not run_id
            run = (
                reconcile_store.latest_run(conn) if is_latest
                else reconcile_store.get_run(conn, run_id)
            )
            if run is None and not is_latest:
                raise NotFound(f"对账批次不存在: {run_id}")
            effective_run_id = run["run_id"] if run else None
            rows, total = reconcile_store.list_findings(
                conn, shop_ids, effective_run_id, kind, status, page, page_size)
            names = {s["id"]: s["name"] for s in shop_store.list(conn)}
        items = [
            {
                **r, "shop_name": names.get(r["shop_id"], ""),
                "kind_title": FINDING_TITLES.get(r["kind"], r["kind"]),
            }
            for r in rows
        ]
        return items, total, _run_view(run)

    def latest_run(self) -> dict | None:
        with self._engine.connect() as conn:
            return _run_view(reconcile_store.latest_run(conn))

    def mark(self, finding_id: int, status: str) -> dict:
        if status not in (STATUS_OPEN, STATUS_HANDLED):
            raise InvalidRequest(f"不支持的处理状态: {status}")
        now = self._now()
        with self._engine.begin() as conn:
            if not reconcile_store.mark_finding(conn, finding_id, status, now):
                raise NotFound(f"对账异常不存在: {finding_id}")
            row = reconcile_store.get_finding(conn, finding_id)
            names = {s["id"]: s["name"] for s in shop_store.list(conn)}
        assert row is not None
        return {
            **row, "shop_name": names.get(row["shop_id"], ""),
            "kind_title": FINDING_TITLES.get(row["kind"], row["kind"]),
        }

    def _now(self) -> str:
        return self._clock().strftime(ISO_FMT)


def _run_view(row: dict | None) -> dict | None:
    """把 shop_ids 的 JSON 文本展开成列表，去掉 schema 之外的多余字段。"""
    if row is None:
        return None
    try:
        shop_ids = json.loads(row.get("shop_ids") or "[]")
    except ValueError:
        shop_ids = []
    return {
        "id": row["id"], "run_id": row["run_id"], "status": row["status"],
        "shop_ids": shop_ids if isinstance(shop_ids, list) else [],
        "window_days": row["window_days"], "started_at": row["started_at"],
        "finished_at": row["finished_at"], "scanned": row["scanned"],
        "finding_count": row["finding_count"], "error": row["error"],
    }


def _shop_job(service: ReconcileService, shop_id: int, run_id: str, window_days: int):
    async def job(client: FxgClient) -> tuple[int, int]:
        return await service._sync_shop(client, shop_id, run_id, window_days)

    return job
