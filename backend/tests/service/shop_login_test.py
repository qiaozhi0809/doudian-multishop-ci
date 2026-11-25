import json
from pathlib import Path

import pytest

from app.adapter.browser.login import LoginCancelled, LoginResult
from app.adapter.doudian.transport import TransportResponse
from app.service.base_data import BaseDataService
from app.service.shop_login import ShopLoginFlow
from tests.fakes import ok
from tests.service.support import PROXY, Env

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "doudian"
NEW_TOKEN = "tok_" + "n" * 8


def fx(name: str) -> TransportResponse:
    return TransportResponse(200, (FIXTURES / f"{name}.json").read_bytes())


class FakeScan:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result, self.error, self.calls = result, error, []

    async def __call__(self, profile_dir, channel, proxy, timeout_s, use_cloak=False):
        self.calls.append((profile_dir, channel, proxy, timeout_s))
        if self.error:
            raise self.error
        return self.result


def make_flow(env, scan, tmp_path) -> ShopLoginFlow:
    base = BaseDataService(env.engine, env.runner, env.events)
    return ShopLoginFlow(env.runner, env.sessions, base, env.events, tmp_path / "profiles",
                         "chrome", scan=scan, timeout_s=7)


def result() -> LoginResult:
    return LoginResult([{"name": "sessionid", "value": "v", "domain": ".jinritemai.com",
                         "path": "/"}], NEW_TOKEN, "2027-01-24T00:00:00Z", {"User-Agent": "UA"})


@pytest.fixture
def env(engine, tmp_path):
    e = Env(engine, tmp_path, responses=[])
    e.sessions.mark_expired(e.shop_id)  # 重新登录场景
    return e


async def test_login_runs_scan_probe_and_base_sync(env, tmp_path):
    scan = FakeScan(result())
    env.transport.responses[:] = [
        ok({"stock_up": 0}), fx("express_list"), fx("address_list"), fx("template_list"),
        fx("ebill_accounts"),
    ]
    await make_flow(env, scan, tmp_path).login(env.shop_id, "admin")
    (profile, channel, proxy, timeout), = scan.calls
    assert profile == tmp_path / "profiles" / str(env.shop_id) and profile.is_dir()
    assert (channel, proxy, timeout) == ("chrome", PROXY, 7)  # 扫码经该店出口
    assert env.shop()["status"] == "active"
    assert env.sessions.get_credentials(env.shop_id).token == NEW_TOKEN
    assert len(env.transport.requests) == 5 and env.transport.responses == []


@pytest.mark.parametrize(("error", "reason"), [
    (TimeoutError(), "扫码超时，请重新发起登录"),
    (LoginCancelled("浏览器已关闭，扫码登录取消"), "浏览器已关闭，扫码登录取消"),
    (RuntimeError("secret internals"), "登录失败，请查看日志"),
])
async def test_login_failure_publishes_event(env, tmp_path, error, reason):
    sub = env.events.subscribe()
    with pytest.raises(type(error)):
        await make_flow(env, FakeScan(error=error), tmp_path).login(env.shop_id, "admin")
    assert await anext(sub) == ("shop_login_failed", {"shop_id": env.shop_id, "reason": reason})
    assert env.shop()["status"] == "needs_login" and env.transport.requests == []


async def test_scan_with_unusable_egress_never_starts(env, tmp_path):
    from app.adapter.doudian.errors import EgressUnavailable

    env.egress.error = EgressUnavailable("down")
    scan = FakeScan(result())
    with pytest.raises(EgressUnavailable):
        await make_flow(env, scan, tmp_path).login(env.shop_id, "admin")
    assert scan.calls == []  # 出口不通时不打开浏览器


async def test_probe_failure_after_scan_reports_and_marks_needs_login(env, tmp_path):
    env.transport.responses[:] = [ok(code=10008)]
    sub = env.events.subscribe()
    from app.adapter.doudian.errors import SessionExpired

    with pytest.raises(SessionExpired):
        await make_flow(env, FakeScan(result()), tmp_path).login(env.shop_id, "admin")
    events = [await anext(sub) for _ in range(3)]
    assert events[-1][0] == "shop_login_failed"
    assert env.shop()["status"] == "needs_login"
    json.dumps(events[-1][1])
