"""售后接口响应 → DTO（docs/api/aftersale.md 附录 E）。"""

from typing import Any

from app.adapter.doudian.errors import ParseError
from app.adapter.doudian.parse_fields import (
    int_fields,
    opt_int,
    opt_str,
    platform_time,
    require_data,
    require_str,
)
from app.domain.aggregate_models import AftersaleDTO


def _parse_item(item: dict) -> AftersaleDTO:
    info = item.get("after_sale_info")
    if not isinstance(info, dict):
        raise ParseError("售后项缺少 after_sale_info")
    return AftersaleDTO(
        after_sale_id=require_str(info, "after_sale_id", "售后单"),
        order_no=opt_str(info.get("related_id")),
        type=opt_int(info.get("after_sale_type")),
        status=opt_int(info.get("after_sale_status")),
        refund_amount_cents=opt_int(info.get("refund_amount")),
        # 平台值为 unix 秒；0 表示已完结 → None（data-model 6.2 ⑯）
        status_deadline=platform_time(info.get("status_deadline")),
        apply_time=platform_time(info.get("apply_time") or info.get("create_time")),
        raw=item,
    )


def parse_aftersale_list(resp: dict) -> tuple[list[AftersaleDTO], int]:
    data = require_data(resp)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ParseError("售后列表缺少 data.items")
    items = [_parse_item(i) for i in data["items"] if isinstance(i, dict)]
    total = opt_int(resp.get("total")) or opt_int(data.get("total"))
    return items, len(items) if total is None else total


def parse_aftersale_counts(resp: dict) -> dict[str, int]:
    """50+ 状态位计数；字段名随平台，只保留整数。"""
    data = require_data(resp)
    if not isinstance(data, dict):
        raise ParseError("售后计数的 data 不是对象")
    return int_fields(data)


def parse_aftersale_detail(resp: dict) -> dict:
    data = require_data(resp)
    if not isinstance(data, dict):
        raise ParseError("售后详情的 data 不是对象")
    return data


def _buttons(raw: dict) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for b in raw.get("buttons") or []:
        if not isinstance(b, dict):
            continue
        code = b.get("button")
        if not code:
            continue
        out.append({
            "code": str(code),
            "text": opt_str(b.get("text") or b.get("button_text")),
            "disabled": bool(b.get("disabled")),
        })
    return out


def aftersale_display(raw: dict) -> dict[str, Any]:
    """从库里的 detail_json（原样报文）提取列表展示字段。

    状态 / 类型 / 原因文案一律用平台下发的成品文案（附录 E.6 第 3 条）。
    """
    info = raw.get("after_sale_info") or {}
    text = raw.get("text_part") or {}
    metrics = raw.get("metrics") or {}
    if not isinstance(info, dict):
        info = {}
    if not isinstance(text, dict):
        text = {}
    if not isinstance(metrics, dict):
        metrics = {}
    return {
        "status_text": opt_str(text.get("after_sale_status_text")),
        "type_text": opt_str(text.get("after_sale_type_text")),
        "reason_text": opt_str(text.get("reason_text")),
        "buyer_nick": opt_str(info.get("encrypted_buyer_info")),
        "left_node_time": opt_int(info.get("left_node_time")),
        "platform_intervene": bool(metrics.get("platform_intervene")),
        "detail_link": opt_str(info.get("detail_link")),
        "buttons": _buttons(raw),
        "order_info": raw.get("order_info") if isinstance(raw.get("order_info"), dict) else {},
    }
