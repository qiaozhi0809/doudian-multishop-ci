"""对账 API：触发、结果查询、筛选、标记与鉴权。"""

from pathlib import Path

from app.adapter.doudian.transport import TransportResponse
from tests.service.label_support import add_account, add_address, add_template

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


def test_run_and_query_findings(api):
    shop_id = ready_shop(api)
    api.transport.queue(TOKEN_A, fx("searchlist_all"))
    started = api.client.post("/api/reconcile/run", json={"window_days": 30})
    assert started.status_code == 202
    run_id = started.json()["run_id"]
    assert started.json()["shop_ids"] == [shop_id]

    api.wait_for(lambda: api.client.get(
        "/api/reconcile/findings", params={"run_id": run_id}).json()["run"]["status"]
        == "success")
    page = api.client.get("/api/reconcile/findings", params={"run_id": run_id}).json()
    assert page["total"] == 2
    assert page["run"]["scanned"] == 3
    assert {i["kind"] for i in page["items"]} == {"platform_shipped_local_not"}
    assert all(i["shop_name"] == "店A" for i in page["items"])

    by_kind = api.client.get("/api/reconcile/findings", params={
        "run_id": run_id, "kind": "waybill_mismatch"}).json()
    assert by_kind["total"] == 0


def test_mark_finding_handled(api):
    ready_shop(api)
    api.transport.queue(TOKEN_A, fx("searchlist_all"))
    run_id = api.client.post("/api/reconcile/run", json={}).json()["run_id"]
    api.wait_for(lambda: api.client.get(
        "/api/reconcile/findings", params={"run_id": run_id}).json()["total"] == 2)
    finding = api.client.get(
        "/api/reconcile/findings", params={"run_id": run_id}).json()["items"][0]
    marked = api.client.patch(
        f"/api/reconcile/findings/{finding['id']}", json={"status": "handled"})
    assert marked.status_code == 200
    assert marked.json()["status"] == "handled"
    handled = api.client.get("/api/reconcile/findings", params={
        "run_id": run_id, "status": "handled"}).json()
    assert handled["total"] == 1


def test_invalid_kind_returns_422(api):
    ready_shop(api)
    resp = api.client.get("/api/reconcile/findings", params={"kind": "bogus"})
    assert resp.status_code == 422
    assert resp.json()["error"]["type"] == "InvalidRequest"


def test_requires_admin(api):
    api.client.cookies.clear()
    assert api.client.get("/api/reconcile/findings").status_code == 401
    assert api.client.post("/api/reconcile/run", json={}).status_code == 401
