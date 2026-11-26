"""分页列表的 SQL 排序：白名单字段、升降方向、空值在后、与分页组合、各列表默认排序。"""

from dataclasses import replace

from app.store import aftersale_store, catalog_store, fund_store, shop_store
from tests.store.aggregate_stores_test import aftersale, product, stock, unsettled
from tests.store.conftest import NOW


def shops(engine, *names: str) -> list[int]:
    with engine.begin() as conn:
        return [shop_store.create(conn, n, NOW) for n in names]


def ids(rows, key: str = "product_id") -> list[str]:
    return [r[key] for r in rows]


def test_stock_default_is_total_stock_ascending_with_unknown_last(engine):
    (a,) = shops(engine, "店A")
    unknown = replace(stock("p-null"), total_stock_num=None)
    with engine.begin() as conn:
        catalog_store.upsert_stock(conn, a, [
            stock("p5", total=5), stock("p0", total=0), unknown, stock("p2", total=2),
        ], NOW)
    with engine.connect() as conn:
        rows, _ = catalog_store.list_stock(conn, [a])
        assert ids(rows) == ["p0", "p2", "p5", "p-null"]
        desc, _ = catalog_store.list_stock(conn, [a], sort="total_stock_num", order="desc")
        assert ids(desc) == ["p5", "p2", "p0", "p-null"]  # 空值降序也在最后


def test_sort_then_paginate_across_pages(engine):
    (a,) = shops(engine, "店A")
    with engine.begin() as conn:
        catalog_store.upsert_products(conn, a, [
            product(f"p{i}", stock_num=i, sell_num=10 - i) for i in range(5)
        ], NOW)
    with engine.connect() as conn:
        first, total = catalog_store.list_products(
            conn, [a], sort="stock_num", order="desc", page=1, page_size=2)
        second, _ = catalog_store.list_products(
            conn, [a], sort="stock_num", order="desc", page=2, page_size=2)
        assert total == 5
        assert ids(first) + ids(second) == ["p4", "p3", "p2", "p1"]  # 整体排序后再切页
        default, _ = catalog_store.list_products(conn, [a])
        assert ids(default) == ["p0", "p1", "p2", "p3", "p4"]  # 默认按销量倒序


def test_products_sort_by_30_day_sales_in_raw_json(engine):
    (a,) = shops(engine, "店A")
    with engine.begin() as conn:
        catalog_store.upsert_products(conn, a, [
            product("p1", raw={"product_id": "p1", "sell_num_30d": 7}),
            product("p2", raw={"product_id": "p2", "sell_num_30d": 30}),
            product("p3", raw={"product_id": "p3"}),
        ], NOW)
    with engine.connect() as conn:
        rows, _ = catalog_store.list_products(conn, [a], sort="sell_num_30d", order="desc")
        assert ids(rows) == ["p2", "p1", "p3"]


def test_products_30_day_sales_sorts_numerically_when_platform_sends_strings(engine):
    (a,) = shops(engine, "店A")
    with engine.begin() as conn:
        catalog_store.upsert_products(conn, a, [
            product("p1", raw={"product_id": "p1", "sell_num_30d": "9"}),
            product("p2", raw={"product_id": "p2", "sell_num_30d": 30}),
            product("p3", raw={"product_id": "p3", "sell_num_30d": "100"}),
        ], NOW)
    with engine.connect() as conn:
        rows, _ = catalog_store.list_products(conn, [a], sort="sell_num_30d", order="desc")
        assert ids(rows) == ["p3", "p2", "p1"]


def test_sort_by_shop_name(engine):
    b, a = shops(engine, "乙店", "甲店")
    with engine.begin() as conn:
        fund_store.replace_unsettled(conn, b, [unsettled("ob")], NOW)
        fund_store.replace_unsettled(conn, a, [unsettled("oa")], NOW)
    with engine.connect() as conn:
        asc, _ = fund_store.list_unsettled(conn, [a, b], sort="shop_name", order="asc")
        desc, _ = fund_store.list_unsettled(conn, [a, b], sort="shop_name", order="desc")
    names = {a: "甲店", b: "乙店"}
    assert [names[r["shop_id"]] for r in asc] == sorted(names.values())
    assert [names[r["shop_id"]] for r in desc] == sorted(names.values(), reverse=True)


def test_aftersale_sort_overrides_deadline_default(engine):
    (a,) = shops(engine, "店A")
    with engine.begin() as conn:
        aftersale_store.upsert_aftersales(conn, a, [
            aftersale("1", deadline="2026-11-26T00:00:00Z", apply="2026-11-20T00:00:00Z"),
            aftersale("2", deadline="2026-11-27T00:00:00Z", apply="2026-11-22T00:00:00Z"),
        ], NOW)
    with engine.connect() as conn:
        todo, _ = aftersale_store.list_aftersales(conn, [a], open_only=True, by_deadline=True)
        latest, _ = aftersale_store.list_aftersales(
            conn, [a], open_only=True, by_deadline=True, sort="apply_time", order="desc")
    assert ids(todo, "after_sale_id") == ["1", "2"]
    assert ids(latest, "after_sale_id") == ["2", "1"]
