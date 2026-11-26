"""API 层测试环境：真实应用 + 假抖店传输 / 假出口探测 / 假扫码。"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.adapter.browser.login import LoginResult
from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.pacer import ShopPacer
from app.adapter.doudian.transport import TransportResponse
from app.config import Settings
from app.main import create_app
from app.service.egress_probe import ProbeResult
from tests.conftest import ADMIN_PASSWORD, ADMIN_USER, FAST_HASHER
from tests.fakes import ok
from tests.service.print_support import FakeComponent

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "doudian"


def fx(name: str) -> TransportResponse:
    return TransportResponse(200, (FIXTURES / f"{name}.json").read_bytes())


def proxy_url(n: int) -> str:
    return f"http://u{n}:pw{n}secret@203.0.113.{n}:8000"


class RoutingTransport:
    """按 __token 区分是哪家店的请求，各自按序返回预设响应。"""

    def __init__(self) -> None:
        self.by_token: dict[str, list] = {}
        self.requests: list[dict] = []

    def queue(self, token: str, *responses) -> None:
        self.by_token.setdefault(token, []).extend(responses)

    async def request(self, method, url, *, params=None, json=None, data=None,
                      cookies=None, headers=None) -> TransportResponse:
        body = json if isinstance(json, dict) else {}
        token = (params or {}).get("__token") or body.get("__token") or ""
        self.requests.append({"method": method, "url": url, "params": params, "token": token})
        queue = self.by_token.get(token)
        assert queue, f"没有为 token={token!r} 预设响应"
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@dataclass
class ApiEnv:
    app: object
    client: TestClient
    transport: RoutingTransport
    print_component: object = None
    ips: dict = field(default_factory=dict)  # 代理 URL -> 探测到的 IP
    scan_impl: object = None
    scan_calls: list = field(default_factory=list)
    events: list = field(default_factory=list)

    # ---- 快捷操作 ----

    def new_shop(self, name: str = "店A", *, ip_n: int | None = 5, checked: bool = True) -> int:
        shop_id = self.client.post("/api/shops", json={"name": name}).json()["id"]
        if ip_n is not None:
            url = proxy_url(ip_n)
            self.ips[url] = f"203.0.113.{ip_n}"
            assert self.client.put(
                f"/api/shops/{shop_id}/egress", json={"mode": "proxy", "proxy_url": url}
            ).status_code == 200
            if checked:
                assert self.client.post(f"/api/shops/{shop_id}/egress/check").status_code == 200
        return shop_id

    def login(self, shop_id: int, token: str) -> None:
        """跳过扫码，直接写入会话（店铺变 active）。"""
        self.app.state.sessions.save_login(shop_id, LoginResult(
            [{"name": "sessionid", "value": "v", "domain": ".jinritemai.com", "path": "/"}],
            token, "2027-01-24T00:00:00Z", {"User-Agent": "UA/1"},
        ))

    def wait_for(self, condition, timeout: float = 3.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if condition():
                return True
            time.sleep(0.01)
        raise AssertionError("等待条件超时")

    def shop(self, shop_id: int) -> dict:
        return next(s for s in self.client.get("/api/shops").json() if s["id"] == shop_id)


@pytest.fixture
def api(tmp_path, clock):
    transport = RoutingTransport()

    def factory(creds, proxy, actor, observer):
        async def no_sleep(_):
            pass

        return FxgClient(transport, creds, ShopPacer(sleep=no_sleep), observer, actor,
                         sleep=no_sleep)

    holder: dict = {}

    async def fetch_ip(proxy):
        return env.ips.get(proxy)

    async def probe(proxy):
        ip = env.ips.get(proxy)
        return ProbeResult(ip, None if ip else "network")

    async def scan(profile_dir, channel, proxy, timeout_s, use_cloak=False, registry=None):
        env.scan_calls.append((profile_dir, channel, proxy, timeout_s))
        return await env.scan_impl(profile_dir, channel, proxy, timeout_s)

    print_component = FakeComponent()
    app = create_app(
        Settings(data_dir=tmp_path / "data", frontend_dist=tmp_path / "no-dist"),
        clock=clock, hasher=FAST_HASHER,
        client_factory=factory, fetch_ip=fetch_ip, scan=scan,
        print_component=print_component, probe=probe,
    )
    with TestClient(app, base_url="http://127.0.0.1:8787") as client:
        client.post("/api/auth/setup", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
        client.post("/api/auth/login", json={"username": ADMIN_USER, "password": ADMIN_PASSWORD})
        env = ApiEnv(app, client, transport, print_component)
        # 记录事件（发布可能来自后台线程，列表追加是线程安全的）
        bus = app.state.events
        original = bus.publish

        def recording(event, data):
            env.events.append((event, data))
            original(event, data)

        bus.publish = recording
        holder["env"] = env
        yield env


def tabcnt_ok(**counts) -> TransportResponse:
    data = {"stock_up": 0, "exp_ship": 0, "ship_delay": 0, "in_aftersale": 0, **counts}
    return TransportResponse(200, json.dumps({"code": 0, "data": data}).encode())


__all__ = ["ok", "fx", "tabcnt_ok", "proxy_url", "api"]
