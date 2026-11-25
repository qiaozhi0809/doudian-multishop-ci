"""M4 测试共用：真实库 + 假出口 + FakeTransport + 数据播种。"""

import asyncio
import time

from app.adapter.browser.login import LoginResult
from app.adapter.doudian.client import FxgClient, ShopCredentials
from app.adapter.doudian.pacer import ShopPacer
from app.service.events import EventBus
from app.service.reconcile import ReconcileService
from app.service.scheduler import ShopScheduler
from app.service.session_manager import SessionManager
from app.service.shipping import ShippingService
from app.service.shop_runner import ShopRunner
from app.shared.secret_box import DevKeyBox
from tests.fakes import FakeTransport
from tests.service.label_support import (
    NOW,
    add_account,
    add_address,
    add_order,
    add_shop,
    add_template,
    add_waybill,
)
from tests.service.support import TOKEN, FakeEgress


class M4Env:
    """一个就绪店铺 + 真实 runner（FakeTransport 回放）+ 发货 / 对账服务。"""

    def __init__(self, engine, tmp_path, clock, responses):
        self.engine = engine
        self.clock = clock
        self.events = EventBus()
        self.sessions = SessionManager(engine, DevKeyBox(tmp_path / "k"), self.events)
        self.egress = FakeEgress()
        self.transport = FakeTransport(list(responses))
        self.runner = ShopRunner(
            engine, ShopScheduler(3), self.egress, self.sessions, self._factory)
        self.shipping = ShippingService(
            engine, self.runner, self.events, clock=clock, sleep=_no_sleep)
        self.reconcile = ReconcileService(engine, self.runner, self.events, clock=clock)
        self.shop_id = add_shop(engine)
        self.sessions.save_login(self.shop_id, LoginResult(
            [{"name": "sessionid", "value": "v", "domain": ".jinritemai.com", "path": "/"}],
            TOKEN, "2027-01-24T00:00:00Z", {"User-Agent": "UA/1"},
        ))
        add_address(engine, self.shop_id)
        add_template(engine, self.shop_id)
        add_account(engine, self.shop_id)

    def _factory(self, creds: ShopCredentials, proxy, actor, observer) -> FxgClient:
        async def no_sleep(_):
            pass

        return FxgClient(self.transport, creds, ShopPacer(sleep=no_sleep), observer, actor,
                         sleep=no_sleep)

    def add_order(self, order_no="o1", **kw) -> int:
        return add_order(self.engine, self.shop_id, order_no, **kw)

    def add_order_for(self, shop_id: int, order_no="o1", **kw) -> int:
        return add_order(self.engine, shop_id, order_no, **kw)

    def add_waybill(self, order_id, **kw) -> int:
        return add_waybill(self.engine, self.shop_id, order_id, **kw)

    def add_waybill_for(self, shop_id: int, order_id, **kw) -> int:
        return add_waybill(self.engine, shop_id, order_id, **kw)

    def order(self, order_id: int) -> dict:
        from app.store import order_store

        with self.engine.connect() as conn:
            return next(o for o in order_store.get_by_ids(conn, [order_id]))

    def shipments(self, batch_id: str) -> list[dict]:
        from app.store import shipping_store

        with self.engine.connect() as conn:
            return shipping_store.by_batch(conn, batch_id)

    def task(self, key: str) -> dict | None:
        from app.store import task_store

        with self.engine.connect() as conn:
            return task_store.get_by_key(conn, key)

    def findings(self, run_id: str | None = None) -> list[dict]:
        from app.store import reconcile_store

        with self.engine.connect() as conn:
            run = (
                reconcile_store.get_run(conn, run_id) if run_id
                else reconcile_store.latest_run(conn)
            )
            if run is None:
                return []
            rows, _ = reconcile_store.list_findings(
                conn, None, run["run_id"], None, None, 1, 200)
            return rows


async def _no_sleep(_: float) -> None:
    pass


async def wait_until(predicate, timeout: float = 3.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("等待条件超时")


NOW_ISO = NOW
