"""service 层测试共用环境：真实库 + 假出口 + FakeTransport。"""

from app.adapter.browser.login import LoginResult
from app.adapter.doudian.client import FxgClient, ShopCredentials
from app.adapter.doudian.pacer import ShopPacer
from app.service.events import EventBus
from app.service.scheduler import ShopScheduler
from app.service.session_manager import SessionManager
from app.service.shop_runner import ShopRunner
from app.shared.secret_box import DevKeyBox
from app.store import shop_store
from tests.fakes import FakeTransport, ok

TOKEN = "tok_" + "x" * 8
PROXY = "http://u1:p1@203.0.113.5:8000"
NOW = "2026-11-25T00:00:00Z"


class FakeEgress:
    def __init__(self) -> None:
        self.ready_calls: list[int] = []
        self.error: Exception | None = None
        self.proxy: str | None = PROXY
        self.unreachable_marks: list[int] = []

    async def ensure_ready(self, shop_id: int) -> None:
        self.ready_calls.append(shop_id)
        if self.error:
            raise self.error

    def proxy_for(self, shop_id: int) -> str | None:
        return self.proxy

    def mark_unreachable(self, shop_id: int) -> None:
        self.unreachable_marks.append(shop_id)


class Env:
    def __init__(self, engine, tmp_path, responses=None):
        self.engine = engine
        self.events = EventBus()
        self.sessions = SessionManager(engine, DevKeyBox(tmp_path / "k"), self.events)
        self.egress = FakeEgress()
        self.transport = FakeTransport(list(responses or [ok({"a": 1})]))
        self.factory_calls: list[tuple] = []
        self.runner = ShopRunner(
            engine, ShopScheduler(3), self.egress, self.sessions, self._factory
        )
        with engine.begin() as conn:
            self.shop_id = shop_store.create(conn, "店A", NOW)
        self.sessions.save_login(self.shop_id, LoginResult(
            [{"name": "sessionid", "value": "v", "domain": ".jinritemai.com", "path": "/"}],
            TOKEN, "2027-01-24T00:00:00Z", {"User-Agent": "UA/1"},
        ))

    def _factory(self, creds: ShopCredentials, proxy, actor, observer) -> FxgClient:
        self.factory_calls.append((creds, proxy, actor))

        async def no_sleep(_):
            pass

        return FxgClient(self.transport, creds, ShopPacer(sleep=no_sleep), observer, actor)

    def shop(self):
        with self.engine.connect() as conn:
            return shop_store.get(conn, self.shop_id)


