"""打印接口：组件状态、提交打印、任务回执、面单可打印信息。"""

import sqlalchemy as sa

from app.store import shop_store, waybill_store
from app.store.schema import order_items, orders
from tests.api.conftest import ok

NOW = "2026-11-25T00:00:00Z"
TOKEN = "tok_print_" + "x" * 6


def infos(*items):
    return ok({"print_infos": list(items)})


def seed_labeled(api, *, order_no="o1", waybill_no="79200000000001",
                 print_data="PD", status="active") -> tuple[int, int]:
    with api.app.state.engine.begin() as conn:
        shop_id = shop_store.create(conn, "店A", NOW)
        order_id = int(conn.execute(sa.insert(orders).values(
            shop_id=shop_id, order_no=order_no, status="label_obtained",
            platform_status=2, synced_at=NOW,
        )).inserted_primary_key[0])
        conn.execute(sa.insert(order_items).values(
            order_id=order_id, sku_order_id="so-" + order_no, sku_id="s1",
            product_id="p1", quantity=1,
        ))
        waybill_id = waybill_store.insert(
            conn, shop_id=shop_id, order_id=order_id, seq=1, courier_code="zhongtong",
            waybill_no=waybill_no, print_data=print_data, sign="SIGN",
            template_code="T1", exp_type="defaultProductType", ebill_id="e1",
            net_code="n1", status=status, now=NOW,
        )
    api.login(shop_id, TOKEN)
    return order_id, waybill_id


def test_print_status_reports_component(api):
    api.print_component.available = True
    body = api.client.get("/api/print/status").json()
    assert body["available"] is True
    assert body["printers"] == ["Printer A"]
    assert body["default_printer"] == "Printer A"
    assert body["error"] is None
    assert body["checked_at"]


def test_print_status_when_component_down(api):
    api.print_component.available = False
    body = api.client.get("/api/print/status").json()
    assert body["available"] is False
    assert body["error"]


def test_submit_runs_jobs_and_reports_success(api):
    api.transport.queue(TOKEN, infos({"tracking_no": "79200000000001",
                                      "template_url": "T"}))
    order_id, waybill_id = seed_labeled(api)

    started = api.client.post("/api/print/jobs", json={"waybill_ids": [waybill_id]})

    assert started.status_code == 202
    job_ids = started.json()["job_ids"]
    assert len(job_ids) == 1
    api.wait_for(
        lambda: api.client.get(f"/api/print/jobs/{job_ids[0]}").json()["status"]
        == "success")
    job = api.client.get(f"/api/print/jobs/{job_ids[0]}").json()
    assert job["attempts"] == 1
    assert job["result_code"] == "success"
    assert api.print_component.print_calls[0][0] == "Printer A"
    pool = api.client.get(
        "/api/print/waybills", params={"waybill_ids": str(waybill_id)}).json()
    row = pool["items"][0]
    assert row["has_print_data"] is True
    assert row["waybill_status"] == "printed"
    assert row["job"]["id"] == job_ids[0]


def test_submit_explicit_printer(api):
    api.transport.queue(TOKEN, infos())
    _, waybill_id = seed_labeled(api)
    body = api.client.post(
        "/api/print/jobs",
        json={"waybill_ids": [waybill_id], "printer_name": "XP-58"}).json()
    api.wait_for(
        lambda: api.client.get(f"/api/print/jobs/{body['job_ids'][0]}").json()["status"]
        == "success")
    assert api.print_component.print_calls[0][0] == "XP-58"


def test_submit_without_component_is_422(api):
    api.print_component.available = False
    _, waybill_id = seed_labeled(api)
    r = api.client.post("/api/print/jobs", json={"waybill_ids": [waybill_id]})
    assert r.status_code == 422
    assert "打印组件" in r.json()["error"]["message"]


def test_void_waybill_is_422(api):
    _, waybill_id = seed_labeled(api, status="void")
    r = api.client.post("/api/print/jobs", json={"waybill_ids": [waybill_id]})
    assert r.status_code == 422


def test_unknown_waybill_is_404(api):
    r = api.client.post("/api/print/jobs", json={"waybill_ids": [999]})
    assert r.status_code == 404


def test_empty_selection_is_422(api):
    r = api.client.post("/api/print/jobs", json={"waybill_ids": []})
    assert r.status_code == 422


def test_unknown_job_is_404(api):
    assert api.client.get("/api/print/jobs/999").status_code == 404


def test_waybills_query_skips_missing(api):
    body = api.client.get("/api/print/waybills", params={"waybill_ids": "999"}).json()
    assert body["items"] == []


def test_requires_admin_session(api):
    api.client.cookies.clear()
    assert api.client.get("/api/print/status").status_code == 401
