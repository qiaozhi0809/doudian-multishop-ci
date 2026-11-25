"""补打面单数据解析（batchGetPrintInfos，flows 10 节）：结构未验证，容错解析。"""

import json

import pytest

from app.adapter.doudian.errors import ParseError
from app.adapter.doudian.print_parsers import parse_print_infos
from app.adapter.doudian.print_request import print_infos_body
from tests.fakes import ok


def resp(data):
    """把 `ok(data)` 的传输响应转成 FxgClient 解析后的 dict。"""
    return json.loads(ok(data).body)


def info(**over):
    base = {
        "tracking_no": "w1", "print_data": "PD", "sign": "S",
        "template_url": "https://example.test/t.xml", "OAuth": "oauth=1",
        "custom_print_data": "CPD", "custom_template_url": "https://example.test/c.xml",
    }
    base.update(over)
    return base


def test_body_carries_tracking_numbers_and_template_code():
    assert print_infos_body(["w1", "w2"]) == {
        "trackInfos": ["w1", "w2"], "templateCode": ""}


def test_parse_list_under_common_keys():
    result = parse_print_infos(resp({"print_infos": [info()]}))
    assert result["w1"].print_data == "PD"
    assert result["w1"].sign == "S"
    assert result["w1"].template_url == "https://example.test/t.xml"
    assert result["w1"].params == "oauth=1"


def test_parse_bare_list_and_camel_case_fields():
    result = parse_print_infos(resp([{
        "trackInfo": "w2", "printData": "PD2", "sign": "S2",
        "templateUrl": "T2", "OAuth": "O2",
    }]))
    assert result["w2"].print_data == "PD2"
    assert result["w2"].template_url == "T2"


def test_parse_mapping_keyed_by_tracking_no():
    result = parse_print_infos(resp({"w3": {"printData": "PD3", "sign": "S3"}}))
    assert result["w3"].print_data == "PD3"


def test_items_without_tracking_no_are_skipped():
    result = parse_print_infos(resp({"print_infos": [{"print_data": "no-track"}, info()]}))
    assert set(result) == {"w1"}


def test_missing_data_raises_parse_error():
    with pytest.raises(ParseError):
        parse_print_infos({"code": 0})
