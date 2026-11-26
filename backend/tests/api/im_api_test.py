"""飞鸽状态接口：只列开启接收的店；手动重新连接在接口层校验。不打开真浏览器。"""

from app.domain.im_rules import STATE_LABELS
from tests.conftest import ADMIN_USER
from tests.service.im_watcher_support import FakeAttach, FakeRegistry

TOKEN_A = "tok_" + "a" * 8


def enable(api, name: str) -> int:
    shop_id = api.new_shop(name, ip_n=None)
    assert api.client.patch(f"/api/shops/{shop_id}", json={"im_enabled": True}).status_code == 200
    return shop_id


def test_requires_admin(api):
    shop_id = enable(api, "测试小铺")
    api.client.cookies.clear()
    assert api.client.get("/api/im/status").status_code == 401
    assert api.client.post(f"/api/im/shops/{shop_id}/restart").status_code == 401


def test_status_lists_enabled_shops(api):
    assert api.client.get("/api/im/status").json() == []
    api.new_shop("未开启小铺", ip_n=None)
    first, second = enable(api, "测试小铺"), enable(api, "测试小店")

    rows = api.client.get("/api/im/status").json()

    assert [(r["shop_id"], r["shop_name"]) for r in rows] == [
        (first, "测试小铺"), (second, "测试小店")]
    assert set(rows[0]) == {
        "shop_id", "shop_name", "state", "state_label", "since", "next_retry_at", "last_error"}
    # 还没扫码登录：已停止，不打开页面
    assert (rows[0]["state"], rows[0]["state_label"]) == ("stopped", STATE_LABELS["stopped"])
    assert rows[0]["next_retry_at"] is None and rows[0]["last_error"] is None


def test_restart_enabled_shop_returns_status(api, monkeypatch):
    shop_id = enable(api, "测试小铺")
    calls: list[tuple[int, str]] = []
    restart = api.app.state.im.restart

    async def record(sid, *, actor):
        calls.append((sid, actor))
        return await restart(sid, actor=actor)

    monkeypatch.setattr(api.app.state.im, "restart", record)

    r = api.client.post(f"/api/im/shops/{shop_id}/restart")

    assert r.status_code == 200
    assert (r.json()["shop_id"], r.json()["shop_name"], r.json()["state"]) == (
        shop_id, "测试小铺", "stopped")
    assert calls == [(shop_id, ADMIN_USER)]


def test_restart_off_shop_rejected(api, monkeypatch):
    shop_id = api.new_shop(ip_n=None)
    monkeypatch.setattr(api.app.state.im, "restart", _must_not_call)

    r = api.client.post(f"/api/im/shops/{shop_id}/restart")

    assert r.status_code == 422 and r.json()["error"]["type"] == "InvalidRequest"


def test_restart_unknown_shop_404(api, monkeypatch):
    monkeypatch.setattr(api.app.state.im, "restart", _must_not_call)

    r = api.client.post("/api/im/shops/999/restart")

    assert r.status_code == 404 and r.json()["error"]["shop_id"] == 999


def test_switch_starts_and_stops_resident_page(api, monkeypatch):
    registry = FakeRegistry()
    monkeypatch.setattr(api.app.state.im, "_browsers", registry)
    monkeypatch.setattr(api.app.state.im, "_attach", FakeAttach())
    shop_id = api.new_shop("测试小铺")
    api.login(shop_id, TOKEN_A)

    def status() -> list[str]:
        return [r["state"] for r in api.client.get("/api/im/status").json()]

    assert api.client.patch(f"/api/shops/{shop_id}", json={"im_enabled": True}).status_code == 200
    api.wait_for(lambda: status() == ["running"])
    assert len(registry.open_contexts()) == 1

    assert api.client.patch(f"/api/shops/{shop_id}", json={"im_enabled": False}).status_code == 200
    api.wait_for(lambda: registry.open_contexts() == [])
    assert status() == []


async def _must_not_call(*_args, **_kwargs):
    raise AssertionError("不该重新连接")
