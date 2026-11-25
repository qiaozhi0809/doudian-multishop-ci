"""平台响应字段读取的公共小工具（M5 解析器共用，纯函数无 IO）。"""

import json
from typing import Any

from app.adapter.doudian.errors import ParseError
from app.shared.time_bj import parse_platform_time

DEFAULT_LIST_KEYS = ("items", "list", "records", "data")
_PAGE_KEYS = ("page", "pagination", "page_info", "pageInfo")


def require_data(resp: dict) -> Any:
    if not isinstance(resp, dict) or "data" not in resp:
        raise ParseError("响应缺少 data")
    return resp["data"]


def require_str(node: dict, key: str, what: str) -> str:
    value = node.get(key)
    if value in (None, ""):
        raise ParseError(f"{what} 缺少 {key}")
    return str(value)


def opt_str(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def opt_int(value: Any) -> int | None:
    """整数或纯数字字符串 → int；其余（含小数点金额）返回 None，由调用方决定换算。"""
    if value is None or isinstance(value, bool) or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.lstrip("-").isdigit():
        return int(text)
    return None


def platform_time(value: Any) -> str | None:
    """平台时间（unix 秒或北京时间字符串）→ ISO-8601 UTC；0 / 空 → None。"""
    try:
        return parse_platform_time(value)
    except ValueError as e:
        raise ParseError(str(e)) from e


def find_list(node: Any, keys: tuple[str, ...] = DEFAULT_LIST_KEYS) -> list | None:
    """在容器（或一层分页子节点）里找列表字段；找不到返回 None（由调用方报 ParseError）。"""
    if isinstance(node, list):
        return node
    if not isinstance(node, dict):
        return None
    for key in keys:
        value = node.get(key)
        if isinstance(value, list):
            return value
    for page_key in _PAGE_KEYS:
        page = node.get(page_key)
        if isinstance(page, dict):
            found = find_list(page, keys)
            if found is not None:
                return found
    return None


def list_with_total(
    resp: dict, keys: tuple[str, ...] = DEFAULT_LIST_KEYS,
) -> tuple[list[dict], int]:
    """取列表与总数：`total` 可能在响应顶层、data 内或分页子节点。"""
    data = require_data(resp)
    rows = find_list(data, keys)
    if rows is None:
        raise ParseError("响应中没有可识别的列表字段")
    if not all(isinstance(r, dict) for r in rows):
        raise ParseError("列表项不是对象")
    total = opt_int(resp.get("total"))
    if total is None and isinstance(data, dict):
        total = opt_int(data.get("total"))
        for page_key in _PAGE_KEYS:
            page = data.get(page_key)
            if total is None and isinstance(page, dict):
                total = opt_int(page.get("total"))
    return rows, len(rows) if total is None else total


def int_fields(node: dict) -> dict[str, int]:
    """只保留整数字段（计数类响应），数字字符串也归一化为 int。"""
    out: dict[str, int] = {}
    for key, value in node.items():
        number = opt_int(value)
        if number is not None:
            out[key] = number
    return out


def order_nos(node: dict) -> tuple[str, ...]:
    """容错提取订单号：`shop_order_list[]` / `shop_order_ids[]` / `shop_order_id`。"""
    out: list[str] = []
    for item in node.get("shop_order_list") or []:
        if isinstance(item, dict) and item.get("shop_order_id"):
            out.append(str(item["shop_order_id"]))
    for key in ("shop_order_ids", "shop_order_id_list"):
        for value in node.get(key) or []:
            out.append(str(value))
    if node.get("shop_order_id"):
        out.append(str(node["shop_order_id"]))
    return tuple(dict.fromkeys(out))


def json_object(value: Any, what: str) -> dict:
    """`data` 里以 JSON 字符串传递的子对象（附录 F.1b）。"""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError as e:
            raise ParseError(f"{what} 不是合法 JSON") from e
        if isinstance(parsed, dict):
            return parsed
    raise ParseError(f"{what} 不是对象")
