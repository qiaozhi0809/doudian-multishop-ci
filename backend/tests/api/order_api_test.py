import sqlalchemy as sa

from app.domain.order_status import LocalOrderStatus
from app.store import order_store
from tests.api.conftest import fx, tabcnt_ok
from tests.fakes import ok
from tests.store.builders import make_item, make_order

TOKEN_A = "tok_" + "a" * 8
TOKEN_B = "tok_" + "b" * 8
NOW = "2026-12-01T00:00:00Z"


def seed_orders(api, shop_id: int, count: int, prefix: str = "o") -> None:
    orders = [
        make_order(f"{prefix}{i:03d}", pay_time=f"2026-11-24T10:{i % 60:02d}:00Z",
                   items=(make_item(f"{prefix}{i}-a"), make_item(f"{prefix}{i}-b")))
        for i in range(count)
    ]
    with api.app.state.engine.begin() as conn:
        order_store.upsert_orders(conn, shop_id, orders, NOW)


def test_orders_paging_one_based(api):
    sid = api.new_shop()
    seed_orders(api, sid, 25)
    assert api.client.get("/api/orders?page=0").status_code == 422
    assert api.client.get("/api/orders?page_size=201").status_code == 422
    assert api.client.get("/api/orders?page_size=0").status_code == 422
    page = api.client.get("/api/orders?page=2&page_size=10").json()
    assert (page["page"], page["page_size"], page["total"], len(page["items"])) == (2, 10, 25, 10)
    last = api.client.get("/api/orders?page=3&page_size=10").json()
    assert len(last["items"]) == 5


def test_order_row_shape_and_items(api):
    sid = api.new_shop("店A")
    seed_orders(api, sid, 1)
    (row,) = api.client.get("/api/orders").json()["items"]
    assert set(row) == {
        "id", "shop_id", "shop_name", "order_no", "platform_status", "status",
        "exception_reason", "amount_cents", "pay_time", "exp_ship_time", "items"}
    assert row["shop_name"] == "店A" and row["status"] == "synced" and row["amount_cents"] == 1000
    assert [i["sku_order_id"] for i in row["items"]] == ["o0-a", "o0-b"]
    assert set(row["items"][0]) == {
        "sku_order_id", "product_id", "product_name", "sku_spec", "quantity", "price_cents"}


def test_orders_filters(api):
    a, b = api.new_shop("A", ip_n=5), api.new_shop("B", ip_n=6)
    seed_orders(api, a, 2, "a")
    seed_orders(api, b, 3, "b")
    with api.app.state.engine.begin() as conn:
        order_store.set_local_status(conn, b, "b001", LocalOrderStatus.PRINTED, NOW)
    assert api.client.get("/api/orders").json()["total"] == 5
    assert api.client.get(f"/api/orders?shop_ids={a}").json()["total"] == 2
    assert api.client.get(f"/api/orders?shop_ids={a},{b}").json()["total"] == 5
    printed = api.client.get("/api/orders?status=printed").json()
    assert [r["order_no"] for r in printed["items"]] == ["b001"]
    assert api.client.get("/api/orders?status=bogus").status_code == 422
    r = api.client.get("/api/orders?shop_ids=abc")
    assert r.status_code == 422 and r.json()["error"]["type"] == "InvalidRequest"
    assert api.client.get("/api/orders?shop_ids=999").status_code == 404


def test_default_listing_excludes_disabled_shops(api):
    a, b = api.new_shop("A", ip_n=5), api.new_shop("B", ip_n=6)
    seed_orders(api, a, 1, "a")
    seed_orders(api, b, 1, "b")
    api.client.patch(f"/api/shops/{b}", json={"enabled": False})
    assert [r["order_no"] for r in api.client.get("/api/orders").json()["items"]] == ["a000"]


def test_counts_partial_failure(api):
    a, b = api.new_shop("A", ip_n=5), api.new_shop("B", ip_n=6)
    api.login(a, TOKEN_A)
    api.login(b, TOKEN_B)
    api.transport.queue(TOKEN_A, tabcnt_ok(stock_up=3, exp_ship=1))
    api.transport.queue(TOKEN_B, ok(code=10008))
    r = api.client.get("/api/orders/counts")
    assert r.status_code == 200
    by_shop = {s["shop_id"]: s for s in r.json()["shops"]}
    assert by_shop[a]["source"] == "upstream" and by_shop[a]["error"] is None
    assert by_shop[a]["counts"] == {"stock_up": 3, "exp_ship": 1, "ship_delay": 0,
                                    "in_aftersale": 0}
    assert by_shop[b]["source"] == "error" and by_shop[b]["counts"] is None
    assert by_shop[b]["error"]
    assert api.shop(b)["status"] == "needs_login"


def test_counts_for_unusable_shops_are_errors_not_failures(api):
    a, b = api.new_shop("A", ip_n=5), api.new_shop("B", ip_n=6)
    api.login(a, TOKEN_A)  # B 从未登录
    api.transport.queue(TOKEN_A, tabcnt_ok(stock_up=1))
    r = api.client.get("/api/orders/counts")
    by_shop = {s["shop_id"]: s for s in r.json()["shops"]}
    assert by_shop[a]["source"] == "upstream" and by_shop[b]["source"] == "error"
    assert [q["token"] for q in api.transport.requests] == [TOKEN_A]  # B 没有发出任何请求


def test_counts_include_paused_shop_as_error(api):
    a = api.new_shop("A", ip_n=5)
    api.login(a, TOKEN_A)
    api.transport.queue(TOKEN_A, ok(code="602502151"))
    assert api.client.post(f"/api/shops/{a}/probe").status_code == 429
    (entry,) = api.client.get("/api/orders/counts").json()["shops"]
    assert entry["source"] == "error" and "暂停" in entry["error"]


def test_manual_sync_goes_through_runner(api):
    a = api.new_shop("A", ip_n=5)
    api.login(a, TOKEN_A)
    api.transport.queue(TOKEN_A, ok(code="602502151"))
    api.client.post(f"/api/shops/{a}/probe")  # 触发风控，暂停该店
    api.transport.requests.clear()
    r = api.client.post(f"/api/orders/sync?shop_ids={a}")
    assert r.status_code == 409 and r.json()["error"]["type"] == "ShopPaused"
    assert r.json()["error"]["shop_id"] == a
    assert api.transport.requests == []


def test_manual_sync_explicit_shop_needs_session(api):
    a = api.new_shop("A", ip_n=5)  # 未登录
    r = api.client.post(f"/api/orders/sync?shop_ids={a}")
    assert r.status_code == 409 and r.json()["error"]["type"] == "SessionExpired"
    assert api.client.post("/api/orders/sync?shop_ids=999").status_code == 404


def test_manual_sync_starts_background_for_runnable_shops(api):
    a, b = api.new_shop("A", ip_n=5), api.new_shop("B", ip_n=6)
    api.login(a, TOKEN_A)  # B 未登录：默认同步直接跳过
    api.transport.queue(TOKEN_A, fx("searchlist_stock_up"))
    r = api.client.post("/api/orders/sync")
    assert r.status_code == 202 and r.json() == {"started": [a], "already_running": []}
    api.wait_for(lambda: api.client.get("/api/orders").json()["total"] == 1)
    row = api.client.get("/api/orders").json()["items"][0]
    assert row["shop_id"] == a and row["platform_status"] == 2
    assert b not in {q["token"] for q in api.transport.requests}


def test_manual_sync_writes_audit_with_admin_actor(api):
    a = api.new_shop("A", ip_n=5)
    api.login(a, TOKEN_A)
    api.transport.queue(TOKEN_A, fx("searchlist_stock_up_empty"))
    api.client.post("/api/orders/sync")
    api.wait_for(lambda: bool(_audit(api)))
    assert _audit(api)[0] == ("admin", "searchlist", "ok")


def _audit(api):
    with api.app.state.engine.connect() as conn:
        return [tuple(r) for r in conn.execute(sa.text(
            "SELECT actor, action, result FROM audit_log WHERE action = 'searchlist'"))]
