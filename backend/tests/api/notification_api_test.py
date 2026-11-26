"""通知接口：列表 / 汇总 / 单条已读 / 全部已读，未登录 401。"""

import sqlalchemy as sa

from app.store.schema import shop

NOW = "2026-12-01T00:00:00Z"


def add_shop(api, name="店A") -> int:
    with api.app.state.engine.begin() as conn:
        return int(conn.execute(sa.insert(shop).values(
            name=name, status="active", created_at=NOW, updated_at=NOW,
        )).inserted_primary_key[0])


def test_list_summary_and_read(api):
    sid = add_shop(api)
    notifications = api.app.state.notifications
    first = notifications.emit("new_order", shop_id=sid, count=3)
    notifications.raise_state("egress", "egress_unreachable", shop_id=sid)

    resp = api.client.get("/api/notifications")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2 and body["page"] == 1
    assert {i["kind"] for i in body["items"]} == {"new_order", "egress_unreachable"}
    item = next(i for i in body["items"] if i["kind"] == "new_order")
    assert item["title"] == "店A 新增 3 单待发货" and item["read_at"] is None
    assert "recovered_notified_at" not in item

    summary = api.client.get("/api/notifications/summary").json()
    assert summary["unread"] == 1  # 未解决的强状态不计未读
    assert summary["strong_open"] == [{
        "shop_id": sid, "shop_name": "店A", "kinds": ["egress_unreachable"],
        "link": f"/shops?shop={sid}",
        "problems": [{"kind": "egress_unreachable", "link": f"/shops?shop={sid}"}],
    }]

    assert api.client.post(f"/api/notifications/{first}/read").status_code == 204
    unread = api.client.get("/api/notifications", params={"unread": 1}).json()
    assert [i["kind"] for i in unread["items"]] == ["egress_unreachable"]

    assert api.client.post("/api/notifications/read-all").status_code == 204
    assert api.client.get("/api/notifications/summary").json()["unread"] == 0
    assert api.client.get("/api/notifications", params={"unread": 0, "page": 1}).json()[
        "total"] == 2


def test_read_unknown_is_404(api):
    assert api.client.post("/api/notifications/9999/read").status_code == 404


def test_notifications_require_admin(api):
    api.client.cookies.clear()
    assert api.client.get("/api/notifications").status_code == 401
    assert api.client.get("/api/notifications/summary").status_code == 401
    assert api.client.post("/api/notifications/1/read").status_code == 401
    assert api.client.post("/api/notifications/read-all").status_code == 401


def test_feed_wired_into_lifespan(api):
    """应用启动后事件经 feed 翻译成通知。"""
    import time

    sid = add_shop(api)
    api.app.state.events.publish("orders_new", {"shop_id": sid, "count": 2})
    for _ in range(100):
        items = api.client.get("/api/notifications").json()["items"]
        if items:
            break
        time.sleep(0.02)
    assert [i["title"] for i in items] == ["店A 新增 2 单待发货"]


def test_daily_backup_purges_old_read_notifications(api):
    import asyncio

    from app.main import _daily_backup
    notifications = api.app.state.notifications
    nid = notifications.emit("reconcile_done", shop_id=None)
    keep = notifications.emit("new_order", shop_id=None)  # 未读：保留
    with api.app.state.engine.begin() as conn:
        conn.execute(sa.text(
            "UPDATE notification SET read_at = :t, updated_at = :t WHERE id = :id"),
            {"t": "2026-10-01T00:00:00Z", "id": nid})
    asyncio.run(_daily_backup(api.app)())
    items = notifications.list(unread_only=False, page=1)["items"]
    assert [i["id"] for i in items] == [keep]
    assert api.app.state.backup.snapshots()[0]["trigger"] == "daily"


def test_purge_failure_does_not_fail_daily_backup(api, monkeypatch):
    import asyncio

    from app.main import _daily_backup

    def boom(_now):
        raise RuntimeError("purge failed")

    monkeypatch.setattr(api.app.state.notifications, "purge", boom)
    result = asyncio.run(_daily_backup(api.app)())
    assert result["trigger"] == "daily"


def test_startup_reconciles_existing_shop_states(app, tmp_path):
    """升级前就登录失效的店：启动后对账一次，补出未解决的登录失效。"""
    import time

    from fastapi.testclient import TestClient

    from app.store import session_store
    from app.store.db import DB_FILE_NAME, make_engine
    from app.store.migrate import upgrade_to_head
    from app.store.session_store import SessionRow

    db = tmp_path / "data" / DB_FILE_NAME
    db.parent.mkdir(parents=True)
    upgrade_to_head(db)
    engine = make_engine(db)
    with engine.begin() as conn:
        sid = int(conn.execute(sa.insert(shop).values(
            name="店A", status="needs_login", created_at=NOW, updated_at=NOW,
        )).inserted_primary_key[0])
        session_store.save(conn, SessionRow(sid, b"c", b"t", "{}", None), NOW)
    engine.dispose()

    with TestClient(app, base_url="http://127.0.0.1:8787"):
        notifications = app.state.notifications
        for _ in range(100):
            if notifications.summary()["strong_open"]:
                break
            time.sleep(0.02)
        (group,) = notifications.summary()["strong_open"]
    assert group["shop_id"] == sid and group["kinds"] == ["login_expired"]
