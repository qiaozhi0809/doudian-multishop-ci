"""打单台 API：订单池、两步提交、作废、按需解密、校验与鉴权。"""

from pathlib import Path

import sqlalchemy as sa

from app.adapter.doudian.transport import TransportResponse
from app.store.schema import waybills
from tests.fakes import ok
from tests.service.label_support import (
    add_account,
    add_address,
    add_order,
    add_template,
    add_waybill,
)

WRITE = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "write"
TOKEN_A = "tok_" + "a" * 8
PT = {"logistics_product": [{"param": "expType", "selectedValue": "defaultProductType"}],
      "added_services": []}


def fx(name: str) -> TransportResponse:
    return TransportResponse(200, (WRITE / f"{name}.json").read_bytes())


def ready_shop(api, name="店A", ip_n=5, token=TOKEN_A) -> int:
    shop_id = api.new_shop(name, ip_n=ip_n)
    api.login(shop_id, token)
    engine = api.app.state.engine
    add_address(engine, shop_id)
    add_template(engine, shop_id)
    add_account(engine, shop_id)
    return shop_id


def test_preview_execute_obtain_then_pool(api):
    shop_id = ready_shop(api)
    oid = add_order(api.app.state.engine, shop_id, "6900000000000000001")
    api.transport.queue(TOKEN_A, ok(PT), fx("batch_fetch_tracking_nos"))

    preview = api.client.post("/api/labels/preview", json={"order_ids": [oid]}).json()
    assert preview["mode"] == "obtain"
    assert preview["total_ready"] == 1
    assert preview["shops"][0]["courier_code"] == "zhongtong"
    assert preview["dry_run"] is False

    resp = api.client.post("/api/labels/execute", json={"preview_id": preview["preview_id"]})
    assert resp.status_code == 202
    assert resp.json()["shop_ids"] == [shop_id]

    api.wait_for(lambda: api.client.get(
        "/api/labels/pool", params={"stage": "labeled"}).json()["total"] == 1)
    labeled = api.client.get("/api/labels/pool", params={"stage": "labeled"}).json()
    assert labeled["items"][0]["waybill"]["waybill_no"] == "79200000000001"
    assert api.client.get("/api/labels/pool").json()["total"] == 0
    assert any(event == "label_done" for event, _ in api.events)
    assert any(event == "label_progress" for event, _ in api.events)


def test_pool_shows_blocked_reason(api):
    shop_id = ready_shop(api)
    add_order(api.app.state.engine, shop_id, "o1", combine_id=None)
    items = api.client.get("/api/labels/pool").json()["items"]
    assert "combine_id" in items[0]["blocked_reason"]


def test_dry_run_execute_returns_409(api):
    shop_id = ready_shop(api)
    oid = add_order(api.app.state.engine, shop_id, "o1")
    api.app.state.label_preview._dry_run = True
    preview = api.client.post("/api/labels/preview", json={"order_ids": [oid]}).json()
    resp = api.client.post("/api/labels/execute", json={"preview_id": preview["preview_id"]})
    assert resp.status_code == 409
    assert resp.json()["error"]["type"] == "DryRunBlocked"


def test_unknown_preview_returns_422(api):
    ready_shop(api)
    resp = api.client.post("/api/labels/execute", json={"preview_id": "nope"})
    assert resp.status_code == 422
    assert resp.json()["error"]["type"] == "InvalidRequest"


def test_mode_mismatch_preview_returns_422(api):
    shop_id = ready_shop(api)
    oid = add_order(api.app.state.engine, shop_id, "o1")
    preview = api.client.post("/api/labels/preview", json={"order_ids": [oid]}).json()
    resp = api.client.post(
        "/api/labels/fetch-and-ship/execute", json={"preview_id": preview["preview_id"]})
    assert resp.status_code == 422


def test_requires_admin(api):
    api.client.cookies.clear()
    assert api.client.get("/api/labels/pool").status_code == 401


def test_void_preview_execute(api):
    shop_id = ready_shop(api)
    oid = add_order(api.app.state.engine, shop_id, "o1", status="label_obtained")
    wid = add_waybill(api.app.state.engine, shop_id, oid, waybill_no="79200000000001")
    api.transport.queue(TOKEN_A, fx("cancel_tracking_nos"))

    preview = api.client.post("/api/labels/void/preview", json={"order_ids": [oid]}).json()
    assert preview["mode"] == "void" and preview["total_ready"] == 1
    assert preview["shops"][0]["waybills"][0]["waybill_id"] == wid

    resp = api.client.post("/api/labels/void/execute", json={"preview_id": preview["preview_id"]})
    assert resp.status_code == 202
    api.wait_for(lambda: api.client.get("/api/labels/pool").json()["total"] == 1)
    with api.app.state.engine.connect() as conn:
        status = conn.execute(sa.select(waybills.c.status).where(
            waybills.c.id == wid)).scalar_one()
    assert status == "void"


def test_receiver_success_and_cooldown(api):
    shop_id = ready_shop(api)
    oid = add_order(api.app.state.engine, shop_id, "6900000000000000001")
    api.transport.queue(TOKEN_A, fx("receiveinfo"))

    first = api.client.post(f"/api/orders/{oid}/receiver")
    assert first.status_code == 200
    assert first.json()["name"] == "张*"
    second = api.client.post(f"/api/orders/{oid}/receiver")
    assert second.json()["cached"] is True
    assert len(api.transport.requests) == 1


def test_receiver_cooldown_returns_429(api):
    shop_id = ready_shop(api)
    oid = add_order(api.app.state.engine, shop_id, "o1")
    api.transport.queue(TOKEN_A, TransportResponse(
        200, b'{"code": "602502151", "msg": "risk"}'))

    resp = api.client.post(f"/api/orders/{oid}/receiver")
    assert resp.status_code == 429
    assert resp.json()["error"]["type"] == "DecryptCooldown"
