"""发货 API：检查、二次确认、提交批次、结果查询与鉴权。"""

from pathlib import Path

from app.adapter.doudian.transport import TransportResponse
from tests.service.label_support import add_account, add_address, add_order, add_template

M4 = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "m4"
TOKEN_A = "tok_" + "a" * 8


def fx(name: str) -> TransportResponse:
    return TransportResponse(200, (M4 / f"{name}.json").read_bytes())


def ready_shop(api, name="店A", ip_n=5, token=TOKEN_A) -> int:
    shop_id = api.new_shop(name, ip_n=ip_n)
    api.login(shop_id, token)
    engine = api.app.state.engine
    add_address(engine, shop_id)
    add_template(engine, shop_id)
    add_account(engine, shop_id)
    return shop_id


def add_shippable(api, shop_id, order_no="6900000000000000001",
                  waybill_no="79200000000001") -> tuple[int, int]:
    engine = api.app.state.engine
    oid = add_order(engine, shop_id, order_no, status="printed")
    from tests.service.label_support import add_waybill

    wid = add_waybill(engine, shop_id, oid, waybill_no=waybill_no)
    return oid, wid


def test_check_and_ship_flow(api):
    shop_id = ready_shop(api)
    oid, _ = add_shippable(api, shop_id)
    api.transport.queue(TOKEN_A, fx("sendcheck"))
    checked = api.client.post("/api/shipping/check", json={"order_ids": [oid]})
    assert checked.status_code == 200
    body = checked.json()
    assert body["total_orders"] == 1
    assert body["shops"][0]["shop_id"] == shop_id
    assert body["double_check_total"] == 0

    api.transport.queue(TOKEN_A, fx("sendcheck"), fx("deliver_goods"))
    started = api.client.post("/api/shipping/ship", json={"order_ids": [oid]})
    assert started.status_code == 202
    batch_id = started.json()["batch_id"]
    assert started.json()["package_count"] == 1

    api.wait_for(lambda: api.client.get(
        f"/api/shipping/batches/{batch_id}").json()["pending"] == 0)
    batch = api.client.get(f"/api/shipping/batches/{batch_id}").json()
    assert batch["ok"] == 1 and batch["failed"] == 0
    assert batch["items"][0]["tracking_no"] == "79200000000001"
    assert api.client.get("/api/shipping/pool").json()["total"] == 0


def test_double_check_blocks_until_acknowledged(api):
    shop_id = ready_shop(api)
    oid, _ = add_shippable(api, shop_id)
    api.transport.queue(TOKEN_A, fx("sendcheck_double"))
    checked = api.client.post("/api/shipping/check", json={"order_ids": [oid]}).json()
    assert checked["double_check_total"] == 1
    assert checked["shops"][0]["double_check_detail"][0]["title"] == "请确认发货信息"

    api.transport.queue(TOKEN_A, fx("sendcheck_double"))
    refused = api.client.post("/api/shipping/ship", json={"order_ids": [oid]})
    assert refused.status_code == 422
    assert refused.json()["error"]["type"] == "InvalidRequest"

    api.transport.queue(TOKEN_A, fx("sendcheck_double"), fx("deliver_goods"))
    ok = api.client.post(
        "/api/shipping/ship", json={"order_ids": [oid], "double_check_ack": True})
    assert ok.status_code == 202


def test_blocked_order_shown_in_check(api):
    shop_id = ready_shop(api)
    oid = add_order(api.app.state.engine, shop_id, "o1", status="pending_label")
    body = api.client.post("/api/shipping/check", json={"order_ids": [oid]}).json()
    assert body["total_orders"] == 0
    assert "没有有效面单" in body["blocked"][0]["reason"]
    assert api.client.post(
        "/api/shipping/ship", json={"order_ids": [oid]}).status_code == 422


def test_dry_run_returns_409(api):
    shop_id = ready_shop(api)
    oid, _ = add_shippable(api, shop_id)
    api.app.state.settings.dry_run = True
    api.app.state.shipping._dry_run = True
    resp = api.client.post("/api/shipping/ship", json={"order_ids": [oid]})
    assert resp.status_code == 409
    assert resp.json()["error"]["type"] == "DryRunBlocked"


def test_requires_admin(api):
    api.client.cookies.clear()
    assert api.client.get("/api/shipping/pool").status_code == 401
    assert api.client.post(
        "/api/shipping/check", json={"order_ids": [1]}).status_code == 401
