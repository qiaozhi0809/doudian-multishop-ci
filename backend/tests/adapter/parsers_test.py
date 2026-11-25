import copy
import json
from pathlib import Path

import pytest

from app.adapter.doudian import parsers
from app.adapter.doudian.errors import ParseError
from app.domain.order_status import PlatformOrderStatus

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "doudian"


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_parse_orders_fields():
    (o,) = parsers.parse_orders(load("searchlist"))
    assert o.order_no == "6900000000000000001"
    assert o.platform_order_id is None and o.combine_id is None
    assert o.platform_status == 4
    assert o.amount_cents == 12800 and isinstance(o.amount_cents, int)
    assert o.create_time == "2026-06-12T10:56:29Z"
    assert o.pay_time == "2026-06-12T10:56:39Z"
    assert o.exp_ship_time == "2026-06-13T15:59:59Z"
    assert (o.buyer_nick, o.receiver_name, o.receiver_phone) == ("测*", "测*", "1**********")
    assert o.receiver_region == "江苏省苏州市吴中区胥口镇"
    (item,) = o.items
    assert item.sku_order_id == "6900000000000000001"
    assert item.product_id == "3811109459833520578"
    assert item.sku_spec == "白色" and item.quantity == 1
    assert item.price_cents == 12800
    assert o.raw["operation_actions"] == ["viewOrder"]


def test_parse_orders_sku_id_zero():
    (closed,) = parsers.parse_orders(load("searchlist"))
    (stock_up,) = parsers.parse_orders(load("searchlist_stock_up"))
    assert closed.items[0].sku_id is None  # 缺 sku_id_str，sku_id 为 0
    assert stock_up.items[0].sku_id is None  # sku_id_str 为空串


def test_parse_orders_sku_id_present():
    resp = load("searchlist_stock_up")
    resp["data"][0]["product_item"][0]["sku_id_str"] = "1700000000000001"
    assert parsers.parse_orders(resp)[0].items[0].sku_id == "1700000000000001"
    resp["data"][0]["product_item"][0].update(sku_id=1700000000000002, sku_id_str="")
    assert parsers.parse_orders(resp)[0].items[0].sku_id == "1700000000000002"


def test_parse_stock_up_order():
    (o,) = parsers.parse_orders(load("searchlist_stock_up"))
    assert o.platform_status == PlatformOrderStatus.STOCK_UP
    assert o.items[0].sku_spec == "蓝色(蓝色)/均码(均码)"
    assert o.raw["operation_actions"] == []


def test_parse_orders_unknown_status():
    resp = load("searchlist_stock_up")
    resp["data"][0]["order_status"] = 99
    assert parsers.parse_orders(resp)[0].platform_status == 99


def test_parse_orders_empty_and_by_order_id():
    assert parsers.parse_orders(load("searchlist_stock_up_empty")) == []
    assert parsers.parse_orders(load("searchlist_by_order_id"))[0].platform_status in {3, 4}


def test_parse_orders_multi_items():
    resp = load("searchlist_stock_up")
    second = copy.deepcopy(resp["data"][0]["product_item"][0])
    second["item_order_id"] = "6900000000000000003"
    second["combo_num"] = 2
    resp["data"][0]["product_item"].append(second)
    items = parsers.parse_orders(resp)[0].items
    assert [i.sku_order_id for i in items] == ["6900000000000000002", "6900000000000000003"]
    assert items[1].quantity == 2


def test_parse_orders_combine_id_when_present():
    resp = load("searchlist_stock_up")
    resp["data"][0]["combine_id"] = "cmb1"
    resp["data"][0]["order_id"] = "pid1"
    o = parsers.parse_orders(resp)[0]
    assert (o.combine_id, o.platform_order_id) == ("cmb1", "pid1")


def test_missing_required_field():
    resp = load("searchlist")
    del resp["data"][0]["shop_order_id"]
    with pytest.raises(ParseError):
        parsers.parse_orders(resp)
    resp = load("searchlist")
    del resp["data"][0]["product_item"][0]["item_order_id"]
    with pytest.raises(ParseError):
        parsers.parse_orders(resp)
    with pytest.raises(ParseError):
        parsers.parse_orders({"code": 0, "data": {"not": "list"}})
    with pytest.raises(ParseError):
        parsers.parse_orders({"code": 0})


def test_parse_tabcnt():
    counts = parsers.parse_tabcnt(load("tabcnt"))
    assert counts["all"] == 1 and counts["closed"] == 1
    for key in ("stock_up", "exp_ship", "ship_delay", "in_aftersale"):
        assert counts[key] == 0
    assert all(isinstance(v, int) for v in counts.values())
    assert "cnt_report" not in counts


def test_parse_addresses_default():
    (a,) = parsers.parse_addresses(load("address_list"))
    assert a.address_id == "90766101" and a.is_default is True
    assert (a.name, a.phone) == ("测试", "138****0000")
    assert (a.province_id, a.city_id, a.town_id, a.street_id) == (
        15, 150500, 150522, 150522100)
    assert a.street_name == "甘旗卡镇" and a.detail == "<详细地址>"
    assert a.region == "内蒙古自治区通辽市科尔沁左翼后旗甘旗卡镇"


def test_parse_addresses_non_default():
    resp = load("address_list")
    resp["data"]["address_list"][0]["is_send_default"] = 0
    resp["data"]["address_list"][0]["is_default"] = 1  # 只看发货默认
    assert parsers.parse_addresses(resp)[0].is_default is False


def test_parse_ebill_accounts_monthly():
    (a,) = parsers.parse_ebill_accounts(load("ebill_accounts"), "jd")
    assert a.courier_code == "jd" and a.ebill_id == "14855496"
    assert a.net_code == "ACCOUNT_PLACEHOLDER" and a.net_name is None
    assert a.balance == -1 and a.account_type == 1 and a.is_default is False


def test_parse_ebill_accounts_camel():
    resp = {"code": 0, "data": {"accounts": [{
        "eBillId": 1, "netCode": "N1", "netName": "网点", "balance": 5,
        "accountType": 2, "isDefault": True,
    }]}}
    (a,) = parsers.parse_ebill_accounts(resp, "zto")
    assert (a.ebill_id, a.net_code, a.net_name, a.balance, a.is_default) == (
        "1", "N1", "网点", 5, True)


def test_parse_ebill_accounts_missing_net_code():
    resp = {"code": 0, "data": {"accounts": [{"eBillId": 1}]}}
    with pytest.raises(ParseError):
        parsers.parse_ebill_accounts(resp, "zto")


def test_parse_templates_custom():
    templates = {t.template_code: t for t in parsers.parse_templates(load("template_list"))}
    assert set(templates) == {"C1lwrn575pfaq2", "jd_76_130"}  # 官方与公共同 code，去重
    custom = templates["C1lwrn575pfaq2"]
    assert custom.is_custom is True and custom.courier_code == "jd" and custom.name == "通天塔"
    official = templates["jd_76_130"]
    assert official.is_custom is False and official.courier_code == "jd"
    assert custom.raw["customTempCode"] == "C1lwrn575pfaq2"


def test_parse_couriers():
    resp = load("express_list")
    resp["data"]["favourites"] = [dict(resp["data"]["eBills"][0]),
                                  {**resp["data"]["eBills"][0], "company": "sf", "name": "顺丰"}]
    couriers = parsers.parse_couriers(resp)
    pairs = [(c.courier_code, c.name) for c in couriers]
    assert pairs == [("jd", "京东物流(常用)"), ("sf", "顺丰")]
    assert all(c.enabled for c in couriers)


def test_parse_couriers_from_fixture():
    (c,) = parsers.parse_couriers(load("express_list"))
    assert c.courier_code == "jd" and c.raw["id"] == 30
