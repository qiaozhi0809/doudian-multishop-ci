"""M2 写接口解析与请求体构造（样本结构见 fixtures/doudian/write/README.md）。"""

import json
from pathlib import Path

import pytest

from app.adapter.doudian.errors import ParseError
from app.adapter.doudian.label_parsers import (
    parse_cancel_result,
    parse_fetch_and_ship_result,
    parse_fetch_result,
    parse_logistics_tracking,
    parse_product_types,
    parse_receiver,
)
from app.adapter.doudian.label_request import cancel_body, fetch_and_ship_body, obtain_body

WRITE = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "write"


def load(name: str) -> dict:
    return json.loads((WRITE / f"{name}.json").read_text(encoding="utf-8"))


# ---- 取号 ----

def test_parse_fetch_success():
    result = parse_fetch_result(load("batch_fetch_tracking_nos"))
    assert len(result.success) == 1
    s = result.success[0]
    assert s.tracking_no == "79200000000001"
    assert s.order_nos == ("6900000000000000001",)
    assert s.courier_code == "zhongtong"
    assert s.template_code == "C1m77ow4c2qrrd"
    assert s.print_data == "PRINT_DATA_PLACEHOLDER"
    assert result.failures == ()


def test_parse_fetch_fail_without_order_refs():
    result = parse_fetch_result(load("batch_fetch_fail"))
    assert result.success == ()
    assert len(result.failures) == 1
    assert result.failures[0].order_nos == ()
    assert "不存在可取号商品" in result.failures[0].fail_msg


def test_parse_fetch_partial_maps_failed_order():
    result = parse_fetch_result(load("batch_fetch_partial_fail"))
    assert result.success[0].order_nos == ("6900000000000000001",)
    assert result.failures[0].order_nos == ("6900000000000000002",)
    assert "超区" in result.failures[0].fail_msg


def test_parse_fetch_success_missing_tracking_becomes_failure():
    resp = load("batch_fetch_tracking_nos")
    del resp["data"]["success_list"][0]["tracking_no"]
    result = parse_fetch_result(resp)
    assert result.success == ()
    assert result.failures[0].order_nos == ("6900000000000000001",)
    assert "运单号" in result.failures[0].fail_msg


def test_parse_fetch_requires_data():
    with pytest.raises(ParseError):
        parse_fetch_result({"code": 0})


# ---- 一体 ----

def test_parse_fetch_and_ship_success():
    result = parse_fetch_and_ship_result(load("fetch_and_ship"))
    assert result.success[0].tracking_no == "79200000000002"
    assert result.success[0].order_nos == ("6900000000000000003",)


# ---- 作废 ----

def test_parse_cancel_success():
    result = parse_cancel_result(load("cancel_tracking_nos"))
    assert result.success[0].tracking_no == "79200000000001"
    assert result.success[0].courier_code == "zhongtong"
    assert result.failures == ()
    assert result.fail_msg is None


def test_parse_cancel_failure_entries():
    resp = load("cancel_tracking_nos")
    resp["data"]["success_list"] = []
    resp["data"]["fail_list"] = [{"logistics_company_code": "zt", "tracking_no": "T1",
                                  "fail_msg": "面单已使用"}]
    resp["data"]["fail_msg"] = "部分失败"
    result = parse_cancel_result(resp)
    assert result.failures[0].fail_msg == "面单已使用"
    assert result.fail_msg == "部分失败"


# ---- 产品类型 ----

def test_parse_product_types_selected_value():
    pt = parse_product_types(load("query_product_types"))
    assert pt.exp_type == "defaultProductType"
    assert pt.added_services == ()


def test_parse_product_types_empty():
    pt = parse_product_types({"code": 0, "data": {"logistics_product": []}})
    assert pt.exp_type is None


# ---- 解密 ----

def test_parse_receiver_fields():
    info = parse_receiver(load("receiveinfo"))
    assert info.name == "张*"
    assert info.phone == "138****0000"
    assert info.region == "内蒙古自治区通辽市科尔沁左翼后旗甘旗卡镇"
    assert info.detail == "<详细地址>"
    assert info.expire_at == "2026-11-30T00:53:20Z"
    assert info.verify_type is None


def test_parse_receiver_verify_type():
    resp = load("receiveinfo")
    resp["data"]["verify_type"] = "slide"
    assert parse_receiver(resp).verify_type == "slide"


def test_parse_receiver_requires_receive_info():
    with pytest.raises(ParseError):
        parse_receiver({"code": 0, "data": {}})


# ---- 查回运单号 ----

def test_parse_logistics_tracking_from_logistics():
    assert parse_logistics_tracking(load("get_order_logistics")) == "79200000000001"


def test_parse_logistics_tracking_none_when_absent():
    assert parse_logistics_tracking({"code": 0, "data": {"logistics": [], "logistics_list": []}}) is None


# ---- 请求体构造（A.2 字段） ----

ADDRESS = {
    "address_id": "106591750", "name": "发货人", "phone": "138****0000",
    "province_id": 15, "province_name": "内蒙古自治区", "city_id": 150500, "city_name": "通辽市",
    "town_id": 150522, "town_name": "科尔沁左翼后旗", "street_id": 150522100,
    "street_name": "甘旗卡镇", "detail": "<详细地址>", "region": "内蒙古自治区通辽市",
}
ORDER_LIST = [{"combine_id": "c1", "is_cancel_combine": False, "shop_order_id": "6900000000000000001",
               "sku_orders": [{"sku_order_id": "so1", "sku_id": "s1", "product_id": "p1",
                               "product_cnt": 1}], "is_sub_bundle_item": True}]


def test_obtain_body_shape():
    body = obtain_body(
        courier_code="zhongtong", template_code="C1m77ow4c2qrrd", address=ADDRESS,
        exp_type="defaultProductType", ebill_id="16103369", net_code="47530",
        order_list=ORDER_LIST,
    )
    assert body["transport"] == json.dumps({"expType": "defaultProductType"})
    assert body["fetch_type"] == 1 and body["order_type"] == 0 and body["version"] == 1
    assert body["address"]["address"] == "内蒙古自治区通辽市科尔沁左翼后旗甘旗卡镇<详细地址>"
    assert body["address"]["id"] == 106591750
    assert "printer" not in body


def test_obtain_body_includes_printer_when_configured():
    body = obtain_body(
        courier_code="zt", template_code="t", address=ADDRESS, exp_type="defaultProductType",
        ebill_id="e", net_code="n", order_list=ORDER_LIST, printer="Printer A",
    )
    assert body["printer"] == "Printer A"


def test_fetch_and_ship_body_shape():
    body = fetch_and_ship_body(
        courier_code="zhongtong", template_code="t", address=ADDRESS,
        exp_type="defaultProductType", ebill_id="e", net_code="n",
        order_list=ORDER_LIST, added_services=(),
    )
    assert body["send_type"] == "3"
    assert body["version"] == 0
    assert body["added_services"] == []
    assert "order_type" not in body


def test_cancel_body_shape():
    body = cancel_body([{"waybill_no": "79200000000001", "courier_code": "zhongtong"}])
    assert body == {"cancel_list": [{"tracking_no": "79200000000001",
                                     "logistics_company_code": "zhongtong"}]}
