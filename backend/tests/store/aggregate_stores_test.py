"""M5 四张聚合表的读写行为（售后 / 商品 / 库存 / 资金）。"""

from app.domain.aggregate_models import (
    AftersaleDTO,
    FundUnsettledDTO,
    MarginDTO,
    ProductDTO,
    StockDTO,
)
from app.store import aftersale_store, catalog_store, fund_store, shop_store
from tests.store.conftest import LATER, NOW


def make_shop(engine, name: str = "店A") -> int:
    with engine.begin() as conn:
        return shop_store.create(conn, name, NOW)


def aftersale(after_sale_id: str, deadline: str | None = None, apply: str = NOW) -> AftersaleDTO:
    return AftersaleDTO(
        after_sale_id=after_sale_id, order_no="6900" + after_sale_id, type=1, status=13,
        refund_amount_cents=12800, status_deadline=deadline, apply_time=apply,
        raw={"after_sale_info": {"after_sale_id": after_sale_id},
             "text_part": {"after_sale_status_text": "待处理"}},
    )


def product(product_id: str, name: str = "商品", **kw) -> ProductDTO:
    base = dict(name=name, status="1", tab="onSale", price_lower_cents=100,
                price_higher_cents=200, stock_num=5, sell_num=1, raw={"product_id": product_id})
    return ProductDTO(product_id=product_id, **{**base, **kw})


def stock(product_id: str, total: int = 5, alarm: bool = False) -> StockDTO:
    return StockDTO(
        product_id=product_id, total_stock_num=total, spot_stock_num=total,
        future_stock_num=0, total_occupied_stock_num=0,
        total_unoccupied_stock_num=total, is_alarming=alarm, raw={"product_id": product_id},
    )


def unsettled(shop_order_no: str, cents: int = 1000) -> FundUnsettledDTO:
    return FundUnsettledDTO(
        shop_order_no=shop_order_no, sku_order_no=shop_order_no + "-1",
        product_id="p1", income_amount_cents=cents + 100,
        unsettled_amount_cents=cents, platform_service_fee_cents=-100,
        ecom_order_status="已发货", expected_settle_time="21天后",
        settle_period_detail='{"delay_day": 21}', raw={"product_name": "商品",
                                                        "shop_order_no": shop_order_no},
    )


# ---- 售后 ----


def test_aftersale_upsert_list_and_deadline_order(engine):
    shop = make_shop(engine)
    with engine.begin() as conn:
        aftersale_store.upsert_aftersales(conn, shop, [
            aftersale("2", deadline="2026-11-27T00:00:00Z"),
            aftersale("1", deadline="2026-11-26T00:00:00Z"),
            aftersale("3", deadline=None),
        ], NOW)
        aftersale_store.upsert_aftersales(conn, shop, [
            aftersale("1", deadline="2026-11-26T00:00:00Z", apply=LATER),
        ], NOW)

    with engine.connect() as conn:
        rows, total = aftersale_store.list_aftersales(conn, [shop])
        assert total == 3
        open_rows, open_total = aftersale_store.list_aftersales(conn, [shop], open_only=True,
                                                                by_deadline=True)
        assert open_total == 2
        assert [r["after_sale_id"] for r in open_rows] == ["1", "2"]
        assert rows[0]["detail_json"]  # 原始报文保留


def test_aftersale_prune_unseen(engine):
    shop = make_shop(engine)
    with engine.begin() as conn:
        aftersale_store.upsert_aftersales(conn, shop, [aftersale("1"), aftersale("2")], NOW)
        aftersale_store.upsert_aftersales(conn, shop, [aftersale("1")], LATER)
        assert aftersale_store.prune_unseen(conn, shop, LATER) == 1

    with engine.connect() as conn:
        rows, _ = aftersale_store.list_aftersales(conn, [shop])
        assert [r["after_sale_id"] for r in rows] == ["1"]


def test_aftersale_keyword_filter(engine):
    shop = make_shop(engine)
    with engine.begin() as conn:
        aftersale_store.upsert_aftersales(conn, shop, [aftersale("100"), aftersale("200")], NOW)
    with engine.connect() as conn:
        rows, total = aftersale_store.list_aftersales(conn, [shop], keyword="100")
        assert total == 1 and rows[0]["after_sale_id"] == "100"


# ---- 商品 / 库存 ----


def test_product_upsert_prune_and_keyword(engine):
    shop = make_shop(engine)
    with engine.begin() as conn:
        catalog_store.upsert_products(conn, shop, [
            product("p1", name="苹果"), product("p2", name="香蕉"),
        ], NOW)
    with engine.connect() as conn:
        rows, total = catalog_store.list_products(conn, [shop], keyword="苹")
        assert total == 1 and rows[0]["name"] == "苹果"
    with engine.begin() as conn:
        catalog_store.upsert_products(conn, shop, [product("p1", name="苹果")], LATER)
        assert catalog_store.prune_products(conn, shop, LATER) == 1


def test_stock_join_name_and_summary(engine):
    shop = make_shop(engine)
    with engine.begin() as conn:
        catalog_store.upsert_products(conn, shop, [product("p1", name="苹果")], NOW)
        catalog_store.upsert_stock(conn, shop, [
            stock("p1", total=5), stock("p2", total=0, alarm=True),
        ], NOW)
    with engine.connect() as conn:
        rows, total = catalog_store.list_stock(conn, [shop])
        assert total == 2
        by_id = {r["product_id"]: r for r in rows}
        assert by_id["p1"]["name"] == "苹果"
        assert by_id["p2"]["is_alarming"] == 1
        alarm_rows, alarm_total = catalog_store.list_stock(conn, [shop], alarm_only=True)
        assert alarm_total == 1 and alarm_rows[0]["product_id"] == "p2"
        summary = catalog_store.stock_summary(conn, [shop])
        assert summary == {"total": 2, "alarm_count": 1, "sold_out_count": 1}


# ---- 资金 ----


def test_unsettled_replace_and_totals(engine):
    shop = make_shop(engine)
    with engine.begin() as conn:
        fund_store.replace_unsettled(conn, shop, [
            unsettled("a", 1000), unsettled("b", 2000),
        ], NOW)
        fund_store.replace_unsettled(conn, shop, [unsettled("a", 1500)], LATER)

    with engine.connect() as conn:
        rows, total = fund_store.list_unsettled(conn, [shop])
        assert total == 1 and rows[0]["unsettled_amount_cents"] == 1500
        assert fund_store.unsettled_totals_by_shop(conn, [shop]) == {shop: (1500, 1)}
        assert fund_store.latest_synced_at(conn, [shop]) == {shop: LATER}


def test_margin_upsert_is_unique_per_shop(engine):
    shop = make_shop(engine)
    first = MarginDTO(payable_cents=0, balance_cents=1000, basic_payable_cents=0,
                      basic_balance_cents=50000, withdrawable_cents=0, level="low", raw={})
    second = MarginDTO(payable_cents=100, balance_cents=2000, basic_payable_cents=0,
                       basic_balance_cents=50000, withdrawable_cents=0, level="low", raw={})
    with engine.begin() as conn:
        fund_store.upsert_margin(conn, shop, first, NOW)
        fund_store.upsert_margin(conn, shop, second, LATER)
    with engine.connect() as conn:
        rows = fund_store.list_margin(conn, [shop])
        assert len(rows) == 1
        assert rows[0]["balance_cents"] == 2000 and rows[0]["synced_at"] == LATER
