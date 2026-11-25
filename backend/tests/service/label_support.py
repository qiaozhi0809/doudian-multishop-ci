"""M2 取号测试共用：真实库 + 假出口 + FakeTransport + 数据播种。"""

import sqlalchemy as sa

from app.adapter.browser.login import LoginResult
from app.adapter.doudian.client import FxgClient, ShopCredentials
from app.adapter.doudian.pacer import ShopPacer
from app.service.events import EventBus
from app.service.label_preview import LabelPreviewService
from app.service.labeling import LabelingService
from app.service.scheduler import ShopScheduler
from app.service.session_manager import SessionManager
from app.service.shop_runner import ShopRunner
from app.shared.secret_box import DevKeyBox
from app.store.schema import (
    ebill_account,
    order_items,
    orders,
    shop,
    shop_address,
    waybill_template,
    waybills,
)
from tests.fakes import FakeTransport
from tests.service.support import TOKEN, FakeEgress

NOW = "2026-11-25T00:00:00Z"


def add_shop(engine, name="店A", status="active") -> int:
    with engine.begin() as conn:
        return int(conn.execute(sa.insert(shop).values(
            name=name, status=status, created_at=NOW, updated_at=NOW,
        )).inserted_primary_key[0])


def add_address(engine, shop_id, address_id="a1", is_default=1) -> None:
    with engine.begin() as conn:
        conn.execute(sa.insert(shop_address).values(
            shop_id=shop_id, address_id=address_id, name="发货人", phone="138****0000",
            region="内蒙古自治区通辽市", detail="<详细地址>", province_id=15,
            province_name="内蒙古自治区", city_id=150500, city_name="通辽市",
            town_id=150522, town_name="科尔沁左翼后旗", street_id=150522100,
            street_name="甘旗卡镇", is_default=is_default, synced_at=NOW,
        ))


def add_template(engine, shop_id, courier="zhongtong", code="T-custom", is_custom=1) -> None:
    with engine.begin() as conn:
        conn.execute(sa.insert(waybill_template).values(
            shop_id=shop_id, template_code=code, courier_code=courier, name="模板",
            is_custom=is_custom, synced_at=NOW,
        ))


def add_account(engine, shop_id, courier="zhongtong", balance=10, is_default=1) -> None:
    with engine.begin() as conn:
        conn.execute(sa.insert(ebill_account).values(
            shop_id=shop_id, courier_code=courier, ebill_id="e1", net_code="n1",
            balance=balance, is_default=is_default, synced_at=NOW,
        ))


def add_order(engine, shop_id, order_no="o1", *, status="pending_label",
              platform_status=2, combine_id: str | None = "c1", sku_id: str | None = "s1") -> int:
    with engine.begin() as conn:
        order_id = int(conn.execute(sa.insert(orders).values(
            shop_id=shop_id, order_no=order_no, status=status,
            platform_status=platform_status, combine_id=combine_id, synced_at=NOW,
        )).inserted_primary_key[0])
        conn.execute(sa.insert(order_items).values(
            order_id=order_id, sku_order_id="so-" + order_no, sku_id=sku_id,
            product_id="p1", quantity=1,
        ))
    return order_id


def add_waybill(engine, shop_id, order_id, *, waybill_no="79200000000001", status="active") -> int:
    with engine.begin() as conn:
        return int(conn.execute(sa.insert(waybills).values(
            shop_id=shop_id, order_id=order_id, seq=1, courier_code="zhongtong",
            waybill_no=waybill_no, status=status, obtained_at=NOW,
        )).inserted_primary_key[0])


class LabelExecEnv:
    """一个就绪店铺 + 真实 runner（FakeTransport 回放）。"""

    def __init__(self, engine, tmp_path, clock, responses, *, dry_run=False,
                 printer_name=""):
        self.engine = engine
        self.clock = clock
        self.events = EventBus()
        self.sessions = SessionManager(engine, DevKeyBox(tmp_path / "k"), self.events)
        self.egress = FakeEgress()
        self.transport = FakeTransport(list(responses))
        self.runner = ShopRunner(
            engine, ShopScheduler(3), self.egress, self.sessions, self._factory)
        self.previews = LabelPreviewService(engine, dry_run=dry_run, clock=clock)
        self.service = LabelingService(
            engine, self.runner, self.previews, self.events,
            printer_name=printer_name, clock=clock, dry_run=dry_run,
        )
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

    def add_waybill(self, order_id, **kw) -> int:
        return add_waybill(self.engine, self.shop_id, order_id, **kw)

    def order(self, order_id: int) -> dict:
        from app.store import order_store

        with self.engine.connect() as conn:
            return next(o for o in order_store.get_by_ids(conn, [order_id]))

    def waybills(self, order_id: int) -> list[dict]:
        from app.store import waybill_store

        with self.engine.connect() as conn:
            return waybill_store.list_by_orders(conn, [order_id])[order_id]

    def task_by_key(self, key: str) -> dict | None:
        from app.store import task_store

        with self.engine.connect() as conn:
            return task_store.get_by_key(conn, key)
