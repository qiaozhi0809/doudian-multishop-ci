import json

import pytest
import sqlalchemy as sa

from app.adapter.browser.login import LoginResult
from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient, ShopCredentials
from app.adapter.doudian.errors import (
    EgressUnavailable,
    RiskBlocked,
    SessionExpired,
)
from app.adapter.doudian.pacer import ShopPacer
from app.service.egress import EgressNotReady
from app.service.events import EventBus
from app.service.scheduler import ShopScheduler
from app.service.session_manager import SessionManager
from app.service.shop_runner import ShopPaused, ShopRunner
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

    async def ensure_ready(self, shop_id: int) -> None:
        self.ready_calls.append(shop_id)
        if self.error:
            raise self.error

    def proxy_for(self, shop_id: int) -> str | None:
        return self.proxy


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


@pytest.fixture
def env(engine, tmp_path):
    return Env(engine, tmp_path)


async def _tabcnt(client):
    return await client.call(ep.TABCNT)


async def test_run_returns_job_result_and_passes_proxy_and_actor(env):
    resp = await env.runner.run(env.shop_id, _tabcnt, actor="admin")
    assert resp["data"] == {"a": 1}
    creds, proxy, actor = env.factory_calls[0]
    assert (creds.token, proxy, actor) == (TOKEN, PROXY, "admin")
    assert env.egress.ready_calls == [env.shop_id]


async def test_paused_shop_skipped(env):
    with env.engine.begin() as conn:
        shop_store.set_paused(conn, env.shop_id, "risk_blocked:602502151", NOW)
    with pytest.raises(ShopPaused):
        await env.runner.run(env.shop_id, _tabcnt, actor="admin")
    assert env.transport.requests == [] and env.egress.ready_calls == []
    assert env.factory_calls == []


async def test_risk_blocked_pauses_shop(env):
    sub = env.events.subscribe()

    async def job(client):
        raise RiskBlocked("602502151", "risk")

    with pytest.raises(RiskBlocked):
        await env.runner.run(env.shop_id, job, actor="admin")
    row = env.shop()
    assert row["paused_reason"] == "risk_blocked:602502151" and row["paused_at"]
    event, data = await anext(sub)
    assert event == "shop_status_changed"
    assert data["shop_id"] == env.shop_id and data["paused_reason"] == "risk_blocked:602502151"


async def test_risk_code_from_response_pauses_shop(env):
    env.transport.responses[:] = [ok(code="10001010A")]
    with pytest.raises(RiskBlocked):
        await env.runner.run(env.shop_id, _tabcnt, actor="admin")
    assert env.shop()["paused_reason"] == "risk_blocked:10001010A"


async def test_session_expired_marks_needs_login(env):
    env.transport.responses[:] = [ok(code=10008)]
    with pytest.raises(SessionExpired):
        await env.runner.run(env.shop_id, _tabcnt, actor="admin")
    assert env.shop()["status"] == "needs_login"
    with pytest.raises(SessionExpired):  # 之后不再发请求
        await env.runner.run(env.shop_id, _tabcnt, actor="admin")
    assert len(env.transport.requests) == 1


@pytest.mark.parametrize("error", [EgressUnavailable("down"), EgressNotReady("dup")])
async def test_egress_unreachable_never_direct(env, error):
    env.egress.error = error
    ran = []

    async def job(client):
        ran.append(1)

    with pytest.raises(type(error)):
        await env.runner.run(env.shop_id, job, actor="admin")
    assert ran == [] and env.transport.requests == [] and env.factory_calls == []


async def test_needs_session_false_runs_without_credentials(env):
    env.sessions.mark_expired(env.shop_id)
    seen = []

    async def job(client):
        seen.append(client)
        return "scanned"

    assert await env.runner.run(env.shop_id, job, actor="admin", needs_session=False) == "scanned"
    creds, proxy, _ = env.factory_calls[0]
    assert creds.cookies == [] and creds.token == "" and proxy == PROXY


async def test_audit_written_with_actor(env):
    await env.runner.run(env.shop_id, _tabcnt, actor="admin")
    with env.engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT * FROM audit_log")).all()
    assert len(rows) == 1
    assert rows[0].actor == "admin" and rows[0].shop_id == env.shop_id
    assert rows[0].action == "tabcnt" and rows[0].result == "ok"
    assert TOKEN not in json.dumps([tuple(r) for r in rows], ensure_ascii=False)


async def test_job_error_still_audited(env):
    env.transport.responses[:] = [ok(code=10008)]
    with pytest.raises(SessionExpired):
        await env.runner.run(env.shop_id, _tabcnt, actor="system")
    with env.engine.connect() as conn:
        row = conn.execute(sa.text("SELECT actor, result FROM audit_log")).one()
    assert tuple(row) == ("system", "SessionExpired")
