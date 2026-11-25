import asyncio

from app.adapter.browser.login import LoginResult
from tests.api.conftest import fx, proxy_url, tabcnt_ok
from tests.fakes import ok

SHOP_ROW_KEYS = {
    "id", "name", "status", "health", "expires_at", "paused_reason", "egress_mode",
    "proxy_display", "egress_ip", "egress_ip_pending", "egress_status", "proxy_expires_at",
    "ready_for_label", "not_ready_reasons",
}
TOKEN_A = "tok_" + "a" * 8


def test_list_shops_fields(api):
    assert api.client.get("/api/shops").json() == []
    shop_id = api.new_shop()
    (row,) = api.client.get("/api/shops").json()
    assert set(row) == SHOP_ROW_KEYS
    assert row["id"] == shop_id and row["status"] == "needs_login" and row["health"] is None
    assert row["egress_mode"] == "proxy" and row["proxy_display"] == "203.0.113.5:8000"
    assert row["egress_ip"] == "203.0.113.5" and row["egress_status"] == "ok"
    assert row["ready_for_label"] is False and row["not_ready_reasons"]
    api.login(shop_id, TOKEN_A)
    row = api.shop(shop_id)
    assert (row["status"], row["health"], row["expires_at"]) == (
        "active", "healthy", "2027-01-24T00:00:00Z")


def test_list_never_exposes_proxy_credentials(api):
    api.new_shop()
    assert "pw5secret" not in api.client.get("/api/shops").text


def test_create_and_patch_shop(api):
    r = api.client.post("/api/shops", json={"name": "  店B  ", "entity": "某主体"})
    assert r.status_code == 201 and r.json()["name"] == "店B"
    sid = r.json()["id"]
    assert api.client.patch(f"/api/shops/{sid}", json={"name": "改名"}).json()["name"] == "改名"
    assert api.client.patch(f"/api/shops/{sid}", json={"channel": "browser"}).status_code == 200
    assert api.client.patch(f"/api/shops/{sid}", json={"enabled": False}).json()["status"] == (
        "disabled")
    assert api.client.patch(f"/api/shops/{sid}", json={"enabled": True}).json()["status"] == (
        "needs_login")


def test_create_and_patch_validation(api):
    assert api.client.post("/api/shops", json={"name": "  "}).status_code == 422
    sid = api.new_shop(ip_n=None)
    assert api.client.patch(f"/api/shops/{sid}", json={"channel": "bogus"}).status_code == 422
    r = api.client.patch("/api/shops/999", json={"name": "x"})
    assert r.status_code == 404 and r.json()["error"]["shop_id"] == 999


def test_put_egress_and_check(api):
    sid = api.new_shop(ip_n=None)
    url = proxy_url(6)
    api.ips[url] = "203.0.113.6"
    r = api.client.put(f"/api/shops/{sid}/egress", json={"mode": "proxy", "proxy_url": url})
    assert r.status_code == 200 and r.json()["egress_status"] == "unchecked"
    assert "pw6secret" not in r.text
    r = api.client.post(f"/api/shops/{sid}/egress/check")
    assert r.json() == {"egress_ip": "203.0.113.6", "egress_ip_pending": None,
                        "egress_status": "ok"}


def test_put_egress_paste_and_rejections(api):
    sid = api.new_shop(ip_n=None)
    r = api.client.put(f"/api/shops/{sid}/egress", json={
        "mode": "proxy", "paste": "203.0.113.7|8000|u7|pw7secret|2026-12-25"})
    assert r.status_code == 200 and r.json()["proxy_expires_at"] == "2026-12-25"
    bad = api.client.put(f"/api/shops/{sid}/egress", json={
        "mode": "proxy", "proxy_url": "socks5://u:pw8secret@203.0.113.8:1080"})
    assert bad.status_code == 422 and bad.json()["error"]["type"] == "InvalidRequest"
    assert "pw8secret" not in bad.text
    assert api.client.put("/api/shops/999/egress", json={"mode": "direct"}).status_code == 404


def test_second_direct_is_conflict(api):
    a = api.client.post("/api/shops", json={"name": "A"}).json()["id"]
    b = api.client.post("/api/shops", json={"name": "B"}).json()["id"]
    assert api.client.put(f"/api/shops/{a}/egress", json={"mode": "direct"}).status_code == 200
    r = api.client.put(f"/api/shops/{b}/egress", json={"mode": "direct"})
    assert r.status_code == 409 and r.json()["error"]["type"] == "EgressConflict"


def test_login_requires_ready_egress(api):
    first = api.new_shop("先建", ip_n=5)
    second = api.new_shop("后建", ip_n=9, checked=False)
    api.ips[proxy_url(9)] = "203.0.113.5"  # 与先建的店出口 IP 相同
    assert first and api.client.post(f"/api/shops/{second}/egress/check").json()[
        "egress_status"] == "duplicate"
    r = api.client.post(f"/api/shops/{second}/login")
    assert r.status_code == 409 and r.json()["error"]["type"] == "EgressNotReady"
    assert api.scan_calls == []  # 没有打开浏览器


def test_login_flow_failure_event(api):
    sid = api.new_shop()

    async def timeout_scan(*_):
        raise TimeoutError

    api.scan_impl = timeout_scan
    assert api.client.post(f"/api/shops/{sid}/login").status_code == 202
    api.wait_for(lambda: any(e == "shop_login_failed" for e, _ in api.events))
    event = next(d for e, d in api.events if e == "shop_login_failed")
    assert event == {"shop_id": sid, "reason": "扫码超时，请重新发起登录"}
    assert api.shop(sid)["status"] == "needs_login"


def test_login_flow_success_runs_probe_and_base_sync(api):
    sid = api.new_shop()

    async def good_scan(profile_dir, channel, proxy, timeout_s):
        return LoginResult([{"name": "sessionid", "value": "v", "domain": ".jinritemai.com",
                             "path": "/"}], TOKEN_A, "2027-01-24T00:00:00Z", {"User-Agent": "UA"})

    api.scan_impl = good_scan
    api.transport.queue(
        TOKEN_A, tabcnt_ok(), fx("express_list"), fx("address_list"), fx("template_list"),
        fx("ebill_accounts"),
    )
    assert api.client.post(f"/api/shops/{sid}/login").status_code == 202
    api.wait_for(lambda: api.shop(sid)["ready_for_label"])
    row = api.shop(sid)
    assert row["status"] == "active"
    (profile, channel, proxy, _), = api.scan_calls
    assert profile.name == str(sid) and proxy == proxy_url(5)  # 扫码经该店出口


def test_second_login_while_running_is_conflict(api):
    sid = api.new_shop()

    async def slow_scan(*_):
        await asyncio.sleep(5)

    api.scan_impl = slow_scan
    assert api.client.post(f"/api/shops/{sid}/login").status_code == 202
    r = api.client.post(f"/api/shops/{sid}/login")
    assert r.status_code == 409 and r.json()["error"]["type"] == "TaskAlreadyRunning"


def test_probe_ok_and_expired(api):
    sid = api.new_shop()
    api.login(sid, TOKEN_A)
    api.transport.queue(TOKEN_A, tabcnt_ok())
    assert api.client.post(f"/api/shops/{sid}/probe").json()["status"] == "active"
    api.transport.queue(TOKEN_A, ok(code=10008))
    r = api.client.post(f"/api/shops/{sid}/probe")
    assert r.status_code == 409 and r.json()["error"]["type"] == "SessionExpired"
    assert api.shop(sid)["status"] == "needs_login"


def test_sync_base_and_view(api):
    sid = api.new_shop()
    api.login(sid, TOKEN_A)
    api.transport.queue(TOKEN_A, fx("express_list"), fx("address_list"), fx("template_list"),
                        fx("ebill_accounts"))
    summary = api.client.post(f"/api/shops/{sid}/sync-base").json()
    assert summary == {"addresses": 1, "couriers": 1, "templates": 2, "accounts": 1,
                       "ready_for_label": True, "not_ready_reasons": []}
    base = api.client.get(f"/api/shops/{sid}/base").json()
    assert [a["address_id"] for a in base["addresses"]] == ["90766101"]
    assert base["addresses"][0]["is_default"] is True
    assert {t["template_code"]: t["is_custom"] for t in base["templates"]} == {
        "C1lwrn575pfaq2": True, "jd_76_130": False}
    assert base["accounts"][0]["balance"] == -1
    assert api.client.get("/api/shops/999/base").status_code == 404


def test_resume_clears_pause(api):
    sid = api.new_shop()
    api.login(sid, TOKEN_A)
    api.transport.queue(TOKEN_A, ok(code="602502151"))
    assert api.client.post(f"/api/shops/{sid}/probe").status_code == 429
    assert api.shop(sid)["paused_reason"] == "risk_blocked:602502151"
    assert api.client.post(f"/api/shops/{sid}/probe").status_code == 409  # 暂停中不再请求
    assert api.client.post(f"/api/shops/{sid}/resume").json()["paused_reason"] is None


def test_requires_admin(api):
    api.client.cookies.clear()
    for method, path in [("GET", "/api/shops"), ("POST", "/api/shops"), ("GET", "/api/orders"),
                         ("GET", "/api/orders/counts"), ("POST", "/api/orders/sync"),
                         ("GET", "/api/events"), ("POST", "/api/shops/1/login")]:
        r = api.client.request(method, path, json={} if method == "POST" else None)
        assert r.status_code == 401, (method, path)
