import json
from pathlib import Path

import pytest

from app.adapter.doudian.aftersale_parsers import (
    aftersale_display,
    parse_aftersale_counts,
    parse_aftersale_detail,
    parse_aftersale_list,
)
from app.adapter.doudian.catalog_parsers import (
    parse_product_counts,
    parse_product_groups,
    parse_products,
    parse_stock,
    parse_warehouses,
)
from app.adapter.doudian.errors import ParseError
from app.adapter.doudian.fund_parsers import (
    bill_amount,
    parse_bills,
    parse_margin,
    parse_unsettled,
    unsettled_display,
)
from app.domain.aftersale_status import pending_total

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "m5"


def fx(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


# ---- 售后 ----


def test_parse_aftersale_list():
    items, total = parse_aftersale_list(fx("aftersale_list"))
    assert (len(items), total) == (2, 2)
    first, done = items
    assert first.after_sale_id == "140000000000000001"
    assert first.order_no == "6900000000000000001"
    assert (first.type, first.status) == (1, 13)
    assert first.refund_amount_cents == 12800
    assert first.status_deadline is not None and first.status_deadline.endswith("Z")
    assert first.apply_time is not None
    # status_deadline = 0 表示已完结 → None（data-model 6.2 ⑯）
    assert done.status_deadline is None


def test_parse_aftersale_counts_and_pending_total():
    counts = parse_aftersale_counts(fx("aftersale_counts"))
    assert counts["total"] == 8
    assert counts["all_audit"] == 1
    # 组级字段相加，不与组内细分重复（all_audit 已含 refund_audit / return_audit）
    assert pending_total(counts) == 2


def test_parse_aftersale_detail_and_display():
    detail = parse_aftersale_detail(fx("aftersale_detail"))
    assert detail["title_info"]["title"] == "退货退款"
    assert len(detail["progress_node"]) == 2

    items, _ = parse_aftersale_list(fx("aftersale_list"))
    display = aftersale_display(items[0].raw)
    assert display["status_text"] == "待商家处理"
    assert display["type_text"] == "退货退款"
    assert display["reason_text"] == "商品与描述不符"
    assert display["buyer_nick"] == "测*"
    assert display["platform_intervene"] is False
    assert [b["code"] for b in display["buttons"]] == ["refund_audit", "handle"]
    assert aftersale_display(items[1].raw)["platform_intervene"] is True


def test_aftersale_list_without_items_is_parse_error():
    with pytest.raises(ParseError):
        parse_aftersale_list({"code": 0, "data": {}})


# ---- 商品 / 库存 ----


def test_parse_products_and_counts():
    items, total = parse_products(fx("product_list"))
    assert (len(items), total) == (2, 2)
    first = items[0]
    assert first.product_id == "3811109459833520578"
    assert first.name == "测试商品 A"
    assert first.status == "1" and first.tab == "onSale"
    assert (first.price_lower_cents, first.price_higher_cents) == (12800, 12800)
    assert first.stock_num == 12 and first.sell_num == 3

    counts = parse_product_counts(fx("product_counts"))
    assert counts == {"onsale": 6, "audit": 0, "unpass": 0, "draft": 0,
                      "forbidden": 0, "sell_out_new": 1}


def test_parse_product_groups():
    groups = parse_product_groups(fx("product_groups"))
    assert [(g.group_id, g.name) for g in groups] == [("1001", "默认分组"), ("1002", "清仓")]


def test_parse_stock_and_warehouses():
    items, summary = parse_stock(fx("stock_list"))
    assert len(items) == 2
    assert summary.total == 2
    assert summary.stock_alarm_cnt == 1 and summary.sold_out_cnt == 1
    assert summary.advised_increase_spot_cnt == 1
    # 现货与未来库存分开保存，不相加（附录 D.4）
    assert (items[0].spot_stock_num, items[0].future_stock_num) == (10, 2)
    assert items[1].is_alarming is True

    warehouses = parse_warehouses(fx("warehouses"))
    assert [(w.warehouse_id, w.name) for w in warehouses] == [("w1", "主仓"), ("w2", "备用仓")]


# ---- 资金 ----


def test_parse_unsettled_second_level_json():
    items, total, total_cents = parse_unsettled(fx("fund_unsettled"))
    assert (len(items), total, total_cents) == (2, 2, 50568)
    first = items[0]
    assert first.shop_order_no == "6900000000000000001"
    assert first.sku_order_no == "6900000000000000001-1"
    assert first.income_amount_cents == 25800
    assert first.platform_service_fee_cents == -516
    assert first.unsettled_amount_cents == 25284
    assert first.ecom_order_status == "已发货"
    assert json.loads(first.settle_period_detail)["delay_day"] == 21

    display = unsettled_display(first.raw)
    assert display["product_name"] == "测试商品 A"
    assert display["settlement_delay_days"] == 21


def test_parse_bills_empty_and_candidate_amounts():
    items, total = parse_bills(fx("fund_bills_empty"))
    assert items == [] and total == 0

    items, total = parse_bills(fx("fund_bills_item"))
    assert total == 2
    confirmed, pending = items
    # 命中候选字段 settle_amount（整数按分）
    assert (confirmed.amount_cents, confirmed.amount_status) == (1234, "confirmed")
    assert confirmed.amount_field == "settle_amount"
    # 全部未命中：记 0 并标注 pending，不用猜测值冒充事实（附录 F.4）
    assert (pending.amount_cents, pending.amount_status) == (0, "pending")
    assert pending.amount_field is None


def test_bill_amount_rules():
    assert bill_amount({"amount_cents": 999}) == (999, "confirmed", "amount_cents")
    # 带小数点按元
    assert bill_amount({"amount": "12.34"}) == (1234, "confirmed", "amount")
    assert bill_amount({"fee": 100}) == (100, "confirmed", "fee")
    assert bill_amount({"bill_no": "B1"}) == (0, "pending", None)


def test_parse_margin_cents():
    margin = parse_margin(fx("fund_margin"))
    assert margin.payable_cents == 0
    assert margin.balance_cents == 1000
    assert margin.basic_balance_cents == 50000
    assert margin.withdrawable_cents == 0
    assert margin.level == "low"


def test_margin_missing_data_is_parse_error():
    with pytest.raises(ParseError):
        parse_margin({"code": 0})


def test_parse_stock_data_as_list_with_top_level_stats():
    # 真实响应同订单列表：data 是数组，统计字段在顶层（docs/api/catalog.md D.2）
    resp = {"code": 0, "data": [
        {"product_id": "1", "total_stock_num": 5, "spot_stock_num": 5, "future_stock_num": 0},
    ], "total": 1, "stock_alarm_cnt": 1, "sold_out_cnt": 0}
    items, summary = parse_stock(resp)
    assert [i.product_id for i in items] == ["1"]
    assert (summary.total, summary.stock_alarm_cnt) == (1, 1)


@pytest.mark.parametrize("data", [None, []])
def test_parse_stock_empty_data(data):
    items, summary = parse_stock({"code": 0, "data": data, "total": 0})
    assert items == [] and summary.total == 0


def test_parse_stock_null_data_without_total_is_empty():
    items, summary = parse_stock({"code": 0, "data": None})
    assert items == [] and summary.total == 0


def test_parse_stock_null_data_with_positive_total_raises():
    # 平台偶发 data=null 但 total>0：必须报错，不能当空店而清掉库存快照
    with pytest.raises(ParseError):
        parse_stock({"code": 0, "data": None, "total": 5})
