"""M3 打印测试环境：真实库 + 假出口 + FakeTransport + FakeComponent。"""

import sqlalchemy as sa

from app.adapter.browser.login import LoginResult
from app.adapter.doudian.client import FxgClient, ShopCredentials
from app.adapter.doudian.pacer import ShopPacer
from app.adapter.print.component import PrinterProbe
from app.adapter.print.protocol import PrintOutcome
from app.service.events import EventBus
from app.service.printing import PrintingService
from app.service.scheduler import ShopScheduler
from app.service.session_manager import SessionManager
from app.service.shop_runner import ShopRunner
from app.shared.secret_box import DevKeyBox
from app.store import shop_store, waybill_store
from app.store.schema import order_items, orders
from tests.fakes import FakeTransport, ok
from tests.service.support import TOKEN, FakeEgress

NOW = "2026-11-25T00:00:00Z"


def infos(*items, **over):
    return ok({"print_infos": list(items), **over})


def info(tracking_no, **fields):
    return {"tracking_no": tracking_no, **fields}


class FakeComponent:
    """按 outcomes 依次返回打印结果；默认成功。"""

    def __init__(self, *, available=True, default_printer="Printer A",
                 printers=("Printer A",), outcomes=None) -> None:
        self.available = available
        self.default_printer = default_printer
        self.printers = printers
        self.outcomes: list[PrintOutcome] = list(outcomes or [])
        self.probe_calls = 0
        self.print_calls: list[tuple[str, list]] = []

    async def probe(self) -> PrinterProbe:
        self.probe_calls += 1
        if not self.available:
            return PrinterProbe(False, error="请先启动抖店官方打印组件")
        return PrinterProbe(True, self.default_printer, tuple(self.printers))

    async def print_documents(self, printer, documents) -> PrintOutcome:
        self.print_calls.append((printer, list(documents)))
        if self.outcomes:
            return self.outcomes.pop(0)
        return PrintOutcome(True, "success", "")


class PrintEnv:
    def __init__(self, engine, tmp_path, clock, responses=None, *, component=None,
                 dry_run=False, default_printer="", events=None, tasks=None):
        self.engine = engine
        self.clock = clock
        self.events = events or EventBus()
        self.sessions = SessionManager(engine, DevKeyBox(tmp_path / "k"), self.events)
        self.egress = FakeEgress()
        self.transport = FakeTransport(list(responses or []))
        self.runner = ShopRunner(
            engine, ShopScheduler(3), self.egress, self.sessions, self._factory)
        self.component = component or FakeComponent()
        self.service = PrintingService(
            engine, self.runner, self.component, self.events, dry_run=dry_run,
            default_printer=default_printer, clock=clock, tasks=tasks)
        with engine.begin() as conn:
            self.shop_id = shop_store.create(conn, "店A", NOW)
        self.sessions.save_login(self.shop_id, LoginResult(
            [{"name": "sessionid", "value": "v", "domain": ".jinritemai.com", "path": "/"}],
            TOKEN, "2027-01-24T00:00:00Z", {"User-Agent": "UA/1"},
        ))

    def _factory(self, creds: ShopCredentials, proxy, actor, observer) -> FxgClient:
        async def no_sleep(_):
            pass

        return FxgClient(self.transport, creds, ShopPacer(sleep=no_sleep), observer, actor,
                         sleep=no_sleep)

    def add_order(self, order_no="o1", *, status="label_obtained") -> int:
        with self.engine.begin() as conn:
            order_id = int(conn.execute(sa.insert(orders).values(
                shop_id=self.shop_id, order_no=order_no, status=status,
                platform_status=2, synced_at=NOW,
            )).inserted_primary_key[0])
            conn.execute(sa.insert(order_items).values(
                order_id=order_id, sku_order_id="so-" + order_no, sku_id="s1",
                product_id="p1", quantity=1,
            ))
        return order_id

    def add_waybill(self, order_id, *, waybill_no="79200000000001", status="active",
                    print_data="PD", sign="SIGN") -> int:
        with self.engine.begin() as conn:
            return waybill_store.insert(
                conn, shop_id=self.shop_id, order_id=order_id, seq=1,
                courier_code="zhongtong", waybill_no=waybill_no, print_data=print_data,
                sign=sign, template_code="T1", exp_type="defaultProductType",
                ebill_id="e1", net_code="n1", status=status, now=NOW,
            )

    def waybill(self, waybill_id: int) -> dict:
        with self.engine.connect() as conn:
            return waybill_store.by_ids(conn, [waybill_id])[0]

    def order(self, order_id: int) -> dict:
        from app.store import order_store

        with self.engine.connect() as conn:
            return order_store.get_by_ids(conn, [order_id])[0]

    def job(self, job_id: int) -> dict:
        from app.store import print_job_store

        with self.engine.connect() as conn:
            return print_job_store.get(conn, job_id)

    def latest_jobs(self, waybill_ids):
        from app.store import print_job_store

        with self.engine.connect() as conn:
            return print_job_store.latest_by_waybills(conn, list(waybill_ids))
