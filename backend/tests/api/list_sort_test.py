"""分页列表的排序参数：白名单与 store 映射一致、非白名单 422、排序与分页组合。"""

from typing import get_args

import pytest

from app.api import list_sort
from app.store import (
    aftersale_store,
    catalog_store,
    fund_store,
    order_store,
    reconcile_store,
)
from tests.api.order_api_test import NOW
from tests.store.builders import make_order

LISTS = [
    "/api/orders",
    "/api/labels/pool",
    "/api/aftersale",
    "/api/aftersale/todo",
    "/api/catalog/products",
    "/api/catalog/stock",
    "/api/fund/unsettled",
    "/api/reconcile/findings",
]


@pytest.mark.parametrize(("literal", "mapping"), [
    (list_sort.OrderSort, order_store.ORDER_SORTS),
    (list_sort.LabelPoolSort, order_store.POOL_SORTS),
    (list_sort.AftersaleSort, aftersale_store.AFTERSALE_SORTS),
    (list_sort.ProductSort, catalog_store.PRODUCT_SORTS),
    (list_sort.StockSort, catalog_store.STOCK_SORTS),
    (list_sort.UnsettledSort, fund_store.UNSETTLED_SORTS),
    (list_sort.FindingSort, reconcile_store.FINDING_SORTS),
])
def test_whitelist_matches_store_mapping(literal, mapping):
    assert set(get_args(literal)) == set(mapping)


@pytest.mark.parametrize("path", LISTS)
def test_unknown_sort_field_or_direction_is_422(api, path):
    assert api.client.get(f"{path}?sort=raw_json").status_code == 422
    assert api.client.get(f"{path}?sort=id;drop").status_code == 422
    assert api.client.get(f"{path}?order=sideways").status_code == 422


def seed(api, shop_id: int, amounts: list[int | None], prefix: str) -> None:
    orders = [
        make_order(f"{prefix}{i}", amount_cents=cents, pay_time=f"2026-11-24T10:{i:02d}:00Z")
        for i, cents in enumerate(amounts)
    ]
    with api.app.state.engine.begin() as conn:
        order_store.upsert_orders(conn, shop_id, orders, NOW)


def order_nos(api, query: str) -> list[str]:
    return [r["order_no"] for r in api.client.get(f"/api/orders?{query}").json()["items"]]


def test_orders_sort_direction_and_paging(api):
    sid = api.new_shop()
    seed(api, sid, [300, 100, None, 500, 200], "o")
    assert order_nos(api, "") == ["o4", "o3", "o2", "o1", "o0"]  # 默认支付时间倒序
    asc = order_nos(api, "sort=amount_cents&order=asc&page_size=2") + order_nos(
        api, "sort=amount_cents&order=asc&page_size=2&page=2") + order_nos(
        api, "sort=amount_cents&order=asc&page_size=2&page=3")
    assert asc == ["o1", "o4", "o0", "o3", "o2"]  # 空金额排最后
    assert order_nos(api, "sort=amount_cents&order=desc") == ["o3", "o0", "o4", "o1", "o2"]
    assert order_nos(api, "sort=amount_cents") == asc  # order 省略为升序


def test_orders_sort_by_shop_name(api):
    b = api.new_shop("店B", ip_n=5)
    a = api.new_shop("店A", ip_n=6)
    seed(api, b, [100], "b")
    seed(api, a, [100], "a")
    assert order_nos(api, "sort=shop_name&order=asc") == ["a0", "b0"]
    assert order_nos(api, "sort=shop_name&order=desc") == ["b0", "a0"]


QUICK_LISTS = [
    ("/api/orders", list_sort.OrderQuick, order_store.ORDER_QUICK_FILTERS),
    ("/api/aftersale", list_sort.AftersaleQuick, aftersale_store.AFTERSALE_QUICK_FILTERS),
    ("/api/aftersale/todo", list_sort.AftersaleQuick, aftersale_store.AFTERSALE_QUICK_FILTERS),
    ("/api/catalog/products", list_sort.ProductQuick, None),
    ("/api/catalog/stock", list_sort.StockQuick, ("alarm", "sold_out")),
]


@pytest.mark.parametrize(("path", "literal", "store_keys"), QUICK_LISTS)
def test_quick_filter_whitelist(api, path, literal, store_keys):
    from app.domain.product_status import PRODUCT_STATE_KEYS

    keys = store_keys if store_keys is not None else PRODUCT_STATE_KEYS
    assert set(get_args(literal)) == set(keys)
    assert api.client.get(f"{path}?quick=raw_json").status_code == 422
    for key in keys:
        assert api.client.get(f"{path}?quick={key}").status_code == 200, key


def test_orders_quick_filter_is_applied_before_paging(api):
    sid = api.new_shop()
    with api.app.state.engine.begin() as conn:
        order_store.upsert_orders(conn, sid, [
            make_order("up1", pay_time="2026-11-24T10:01:00Z"),
            make_order("shipped", platform_status=3, pay_time="2026-11-24T10:02:00Z"),
            make_order("up2", pay_time="2026-11-24T10:03:00Z"),
        ], NOW)
    body = api.client.get("/api/orders?quick=stock_up&page_size=1").json()
    assert body["total"] == 2 and [r["order_no"] for r in body["items"]] == ["up2"]
