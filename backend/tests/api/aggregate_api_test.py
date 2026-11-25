import json
from pathlib import Path

from tests.api.conftest import proxy_url
from tests.fakes import reply

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "m5"
TOKEN = "tok_" + "m" * 8


def fx_response(name: str):
    return reply(json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8")))


def setup_shop(api, name: str = "店A", shop_no: str | None = None) -> int:
    body: dict = {"name": name}
    if shop_no:
        body["shop_no"] = shop_no
    shop_id = api.client.post("/api/shops", json=body).json()["id"]
    url = proxy_url(5)
    api.ips[url] = "203.0.113.5"
    assert api.client.put(
        f"/api/shops/{shop_id}/egress", json={"mode": "proxy", "proxy_url": url}
    ).status_code == 200
    assert api.client.post(f"/api/shops/{shop_id}/egress/check").status_code == 200
    api.login(shop_id, TOKEN)
    return shop_id


def sync_url(path: str) -> str:
    return f"/api/{path}"


def test_aftersale_sync_list_todo_counts_detail(api):
    shop_id = setup_shop(api)
    api.transport.queue(TOKEN, fx_response("aftersale_list"))
    started = api.client.post(sync_url("aftersale/sync")).json()
    assert started["shops"][0]["fetched"] == 2
    assert started["shops"][0]["complete"] is True
    assert started["shops"][0]["error"] is None

    page = api.client.get("/api/aftersale").json()
    assert (page["total"], len(page["items"])) == (2, 2)
    row = next(r for r in page["items"] if r["after_sale_id"] == "140000000000000001")
    assert row["shop_name"] == "店A"
    assert row["refund_amount_cents"] == 12800
    assert row["display"]["status_text"] == "待商家处理"
    assert [b["code"] for b in row["display"]["buttons"]] == ["refund_audit", "handle"]

    todo = api.client.get("/api/aftersale/todo").json()
    assert todo["total"] == 1
    assert todo["items"][0]["after_sale_id"] == "140000000000000001"
    assert api.client.get("/api/aftersale?pending=true").json()["total"] == 1
    assert api.client.get("/api/aftersale?keyword=140000000000000002").json()["total"] == 1

    statuses = api.client.get("/api/aftersale/statuses").json()["items"]
    assert {"status": 13, "label": "待商家处理"} in statuses

    api.transport.queue(TOKEN, fx_response("aftersale_counts"))
    counts = api.client.get("/api/aftersale/counts").json()["shops"][0]
    assert counts["source"] == "upstream"
    assert counts["pending_total"] == 2
    assert counts["counts"]["total"] == 8

    api.transport.queue(TOKEN, fx_response("aftersale_detail"))
    detail = api.client.get(
        f"/api/aftersale/140000000000000001?shop_id={shop_id}"
    ).json()
    assert detail["detail"]["title_info"]["title"] == "退货退款"


def test_catalog_products_and_stock(api):
    setup_shop(api)
    api.transport.queue(TOKEN, fx_response("product_list"))
    synced = api.client.post("/api/catalog/products/sync").json()["shops"][0]
    assert (synced["fetched"], synced["complete"]) == (2, True)

    page = api.client.get("/api/catalog/products").json()
    assert page["total"] == 2
    row = page["items"][0]
    assert row["shop_name"] == "店A"
    assert row["display"]["category_name"] == "测试类目"
    assert api.client.get("/api/catalog/products?keyword=商品 A").json()["total"] == 1

    api.transport.queue(TOKEN, fx_response("product_counts"))
    counts = api.client.get("/api/catalog/products/counts").json()["shops"][0]
    assert counts["counts"]["onsale"] == 6

    api.transport.queue(TOKEN, fx_response("product_groups"))
    groups = api.client.get("/api/catalog/products/groups").json()["shops"][0]
    assert groups["items"] == [{"group_id": "1001", "name": "默认分组"},
                               {"group_id": "1002", "name": "清仓"}]

    api.transport.queue(TOKEN, fx_response("product_list"), fx_response("stock_list"))
    api.client.post("/api/catalog/products/sync")
    stock_sync = api.client.post("/api/catalog/stock/sync").json()["shops"][0]
    assert (stock_sync["fetched"], stock_sync["alarm_count"]) == (2, 1)

    stock = api.client.get("/api/catalog/stock").json()
    assert stock["total"] == 2
    assert {r["product_id"]: r["name"] for r in stock["items"]}["3811109459833520578"] == (
        "测试商品 A"
    )
    assert api.client.get("/api/catalog/stock?alarm_only=true").json()["total"] == 1
    assert api.client.get("/api/catalog/stock/summary").json() == {
        "total": 2, "alarm_count": 1, "sold_out_count": 1,
    }

    api.transport.queue(TOKEN, fx_response("warehouses"))
    warehouses = api.client.get("/api/catalog/stock/warehouses").json()["shops"][0]
    assert [w["warehouse_id"] for w in warehouses["items"]] == ["w1", "w2"]


def test_fund_sync_summary_unsettled_margin_bills(api):
    setup_shop(api, shop_no="62000070001")
    api.transport.queue(TOKEN, fx_response("fund_unsettled"), fx_response("fund_margin"))
    synced = api.client.post("/api/fund/sync").json()["shops"][0]
    assert (synced["unsettled_count"], synced["margin_synced"]) == (2, True)

    summary = api.client.get("/api/fund/summary").json()
    assert summary["total_unsettled_amount_cents"] == 50568
    assert summary["total_unsettled_count"] == 2
    assert summary["shops"][0]["margin_balance_cents"] == 1000

    unsettled = api.client.get("/api/fund/unsettled").json()
    assert unsettled["total"] == 2
    assert unsettled["items"][0]["display"]["settlement_delay_days"] == 21

    margins = api.client.get("/api/fund/margin").json()["items"]
    assert len(margins) == 1
    assert margins[0]["basic_balance_cents"] == 50000

    api.transport.queue(TOKEN, fx_response("fund_bills_empty"))
    bills = api.client.get("/api/fund/bills?days=7").json()
    assert bills["days"] == 7
    assert bills["shops"][0]["source"] == "upstream"
    assert (bills["shops"][0]["total"], bills["shops"][0]["items"]) == (0, [])


def test_aggregate_queries_require_login(client):
    assert client.get("/api/aftersale").status_code == 401
    assert client.get("/api/catalog/products").status_code == 401
    assert client.get("/api/fund/summary").status_code == 401
