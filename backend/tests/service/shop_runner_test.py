import asyncio
import json

import pytest
import sqlalchemy as sa

from app.adapter.browser.login import LoginResult
from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.errors import (
    EgressUnavailable,
    RiskBlocked,
    SessionExpired,
)
from app.service.egress import EgressNotReady, EgressService
from app.service.scheduler import ShopScheduler
from app.service.shop_runner import ShopPaused, ShopRunner
from app.shared.secret_box import DevKeyBox
from app.store import shop_store
from tests.fakes import ok
from tests.service.support import PROXY, TOKEN, Env, FakeEgress  # noqa: F401

NOW = "2026-11-25T00:00:00Z"


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


async def test_queued_jobs_stop_after_risk_pause(env):
    env.transport.responses[:] = [ok(code="602502151")]

    async def job(client):
        await asyncio.sleep(0.01)  # 让后两个任务都通过进队列前的检查，排在锁后面
        return await client.call(ep.TABCNT)

    results = await asyncio.gather(
        *[env.runner.run(env.shop_id, job, actor="admin") for _ in range(3)],
        return_exceptions=True,
    )
    assert isinstance(results[0], RiskBlocked)
    assert all(isinstance(r, ShopPaused) for r in results[1:])
    assert len(env.transport.requests) == 1


async def test_egress_failure_mid_job_invalidates_cache(engine, tmp_path):
    env = Env(engine, tmp_path)
    ips = {PROXY: "203.0.113.5"}
    fetched: list = []

    async def fetch_ip(proxy):
        fetched.append(proxy)
        return ips.get(proxy)

    egress = EgressService(engine, DevKeyBox(tmp_path / "k2"), env.events, fetch_ip)
    egress.set_egress(env.shop_id, "proxy", proxy_url=PROXY)
    await egress.check(env.shop_id)
    env.sessions.save_login(env.shop_id, LoginResult([], TOKEN, "2027-01-24T00:00:00Z", {}))
    runner = ShopRunner(engine, ShopScheduler(3), egress, env.sessions, env._factory)

    async def job(client):
        raise EgressUnavailable("proxy dropped")

    with pytest.raises(EgressUnavailable):
        await runner.run(env.shop_id, job, actor="admin")
    assert env.shop()["egress_status"] == "unreachable"

    ips[PROXY] = None  # 代理仍然不通
    ran = []

    async def second(client):
        ran.append(1)

    before = len(fetched)
    with pytest.raises(EgressUnavailable):
        await runner.run(env.shop_id, second, actor="admin")
    assert len(fetched) == before + 1  # 没走 10 分钟缓存，重新探测了
    assert ran == []
