"""飞鸽接口：接收状态、手动重新连接、会话列表与计数、消息记录、在飞鸽中回复。不打开真浏览器。"""

from app.domain.im_rules import STATE_LABELS
from app.service.im_session import ConvView
from app.store import im_message_store
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


# ---- 会话列表、计数、消息记录（时钟固定在 2026-12-01T00:00:00Z） ----

_ROW_KEYS = {
    "shop_id", "shop_name", "conversation_id", "buyer", "preview", "unread", "last_at",
    "waiting_since", "wait_seconds",
}


def conv(conversation_id: str, *, last: str, waiting: str | None = None, pending: int = 0):
    """last / waiting：2026-11-30 23 点内的「分:秒」。"""
    return ConvView(
        conversation_id, None, "在吗", "buyer", f"2026-11-30T23:{last}Z", pending,
        None if waiting is None else f"2026-11-30T23:{waiting}Z", "测试买家",
    )


def two_shops(api, monkeypatch) -> tuple[int, int]:
    first, second = enable(api, "测试小铺"), enable(api, "测试小店")
    views = {
        first: [
            conv("conv-test-1", last="59:00", waiting="59:00", pending=1),
            conv("conv-test-2", last="59:50"),
        ],
        second: [conv("conv-test-3", last="50:00", waiting="50:00", pending=2)],
    }
    monkeypatch.setattr(api.app.state.im, "snapshot", lambda shop_id: views.get(shop_id, []))
    return first, second


def ids(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [r["conversation_id"] for r in response.json()["items"]]


def test_conversations_requires_admin(api):
    shop_id = enable(api, "测试小铺")
    api.client.cookies.clear()

    for path in (
        "/api/im/conversations", "/api/im/conversations/counts",
        f"/api/im/conversations/{shop_id}/conv-test-1/messages",
    ):
        assert api.client.get(path).status_code == 401, path


def test_conversations_default_sort_waiting_desc(api, monkeypatch):
    _, second = two_shops(api, monkeypatch)

    r = api.client.get("/api/im/conversations")

    assert ids(r) == ["conv-test-3", "conv-test-1", "conv-test-2"]
    body = r.json()
    assert (body["total"], body["page"], body["page_size"]) == (3, 1, 50)
    top = body["items"][0]
    assert set(top) == _ROW_KEYS
    assert (top["shop_id"], top["shop_name"], top["buyer"], top["preview"]) == (
        second, "测试小店", "测试买家", "在吗")
    assert (top["unread"], top["wait_seconds"]) == (2, 600)
    assert body["items"][2]["wait_seconds"] is None


def test_conversations_filters_sort_and_page(api, monkeypatch):
    two_shops(api, monkeypatch)
    get = api.client.get

    assert ids(get("/api/im/conversations?unread=true&sort=unread&order=asc")) == [
        "conv-test-1", "conv-test-3"]
    assert ids(get("/api/im/conversations?quick=overdue")) == ["conv-test-3"]
    r = get("/api/im/conversations?page=2&page_size=2")
    assert (ids(r), r.json()["total"]) == (["conv-test-2"], 3)


def test_conversations_bad_sort_or_quick_422(api):
    for query in (
        "sort=preview", "quick=all", "order=up", "page=0", "page_size=201", "shop_ids=x",
    ):
        assert api.client.get(f"/api/im/conversations?{query}").status_code == 422, query


def test_conversations_shop_filter(api, monkeypatch):
    first, _ = two_shops(api, monkeypatch)

    assert ids(api.client.get(f"/api/im/conversations?shop_ids={first}")) == [
        "conv-test-1", "conv-test-2"]
    assert api.client.get("/api/im/conversations?shop_ids=999").status_code == 404
    counts = api.client.get(f"/api/im/conversations/counts?shop_ids={first}").json()
    assert counts["unread"] == 1


def test_counts_shape(api, monkeypatch):
    two_shops(api, monkeypatch)

    r = api.client.get("/api/im/conversations/counts")

    # 北京时间 2026-12-01 08:00 看，这些消息都在今天 07 点多
    assert r.status_code == 200
    assert r.json() == {"unread": 2, "waiting": 2, "overdue": 1, "today": 3}


def test_messages_ok(api):
    shop_id = enable(api, "测试小铺")
    with api.app.state.engine.begin() as conn:
        im_message_store.insert_ignore(conn, shop_id, [{
            "conversation_id": "conv-test-1", "message_id": "msg-test-1", "sender_role": "buyer",
            "text": "在吗", "sent_at": "2026-11-30T23:59:00Z",
        }], "2026-11-30T23:59:01Z")

    r = api.client.get(f"/api/im/conversations/{shop_id}/conv-test-1/messages")

    assert r.status_code == 200
    assert r.json() == {"shop_id": shop_id, "conversation_id": "conv-test-1", "items": [{
        "message_id": "msg-test-1", "sender_role": "buyer", "text": "在吗",
        "sent_at": "2026-11-30T23:59:00Z",
    }]}


def test_messages_bad_conversation_id_422(api):
    shop_id = enable(api, "测试小铺")

    for bad in ("conv$1", "conv%20test", "a" * 129):
        r = api.client.get(f"/api/im/conversations/{shop_id}/{bad}/messages")
        assert r.status_code == 422, bad


def test_messages_unknown_404(api):
    shop_id = enable(api, "测试小铺")

    unknown = api.client.get(f"/api/im/conversations/{shop_id}/conv-test-9/messages")
    no_shop = api.client.get("/api/im/conversations/999/conv-test-1/messages")

    assert unknown.status_code == 404 and unknown.json()["error"]["shop_id"] == shop_id
    assert no_shop.status_code == 404 and no_shop.json()["error"]["shop_id"] == 999


# ---- 在飞鸽中回复 ----


def open_path(shop_id: int, conversation_id: str = "conv-test-1") -> str:
    return f"/api/im/conversations/{shop_id}/{conversation_id}/open-in-flybird"


def receiving_shop(api, monkeypatch) -> tuple[int, FakeAttach]:
    """假浏览器上跑起一家店的常驻页。"""
    attach = FakeAttach()
    monkeypatch.setattr(api.app.state.im, "_browsers", FakeRegistry())
    monkeypatch.setattr(api.app.state.im, "_attach", attach)
    shop_id = api.new_shop("测试小铺")
    api.login(shop_id, TOKEN_A)
    assert api.client.patch(f"/api/shops/{shop_id}", json={"im_enabled": True}).status_code == 200
    api.wait_for(
        lambda: [r["state"] for r in api.client.get("/api/im/status").json()] == ["running"])
    return shop_id, attach


def test_open_in_flybird_ok(api, monkeypatch):
    shop_id, attach = receiving_shop(api, monkeypatch)
    page = attach.pages[0].page
    page.conversations = ["测试买家 在吗"]

    r = api.client.post(open_path(shop_id))

    assert r.status_code == 200 and r.json() == {"result": "opened"}
    assert page.clicked() == ["测试买家 在吗"]
    page.conversations = []
    assert api.client.post(open_path(shop_id)).json() == {"result": "not_found"}


def test_open_in_flybird_not_running_422(api):
    shop_id = enable(api, "测试小铺")  # 还没扫码登录：没有常驻页

    r = api.client.post(open_path(shop_id))

    assert r.status_code == 422
    assert r.json()["error"]["type"] == "InvalidRequest"
    assert r.json()["error"]["message"] == "该店飞鸽未在接收"


def test_open_in_flybird_requires_admin(api):
    shop_id = enable(api, "测试小铺")
    api.client.cookies.clear()

    assert api.client.post(open_path(shop_id)).status_code == 401


def test_open_in_flybird_unknown_shop_404_and_bad_id_422(api, monkeypatch):
    monkeypatch.setattr(api.app.state.im, "focus", _must_not_call)
    shop_id = enable(api, "测试小铺")

    assert api.client.post(open_path(999)).status_code == 404
    assert api.client.post(open_path(shop_id, "conv$1")).status_code == 422


async def _must_not_call(*_args, **_kwargs):
    raise AssertionError("不该调用")
