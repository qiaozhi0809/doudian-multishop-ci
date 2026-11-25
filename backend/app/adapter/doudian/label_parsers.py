"""取号 / 一体 / 作废 / 解密 / 物流查询的响应解析（依据 write.md A.2 与 read.md A.1）。"""

from typing import Any

from app.adapter.doudian.errors import ParseError
from app.adapter.doudian.parse_fields import order_nos
from app.domain.models import (
    CancelFailure,
    CancelResult,
    CancelSuccess,
    FetchFailure,
    FetchResult,
    FetchSuccess,
    ProductTypes,
    ReceiverInfo,
)
from app.shared.time_bj import parse_platform_time


def _data(resp: dict) -> dict:
    data = resp.get("data") if isinstance(resp, dict) else None
    if not isinstance(data, dict):
        raise ParseError("响应缺少 data")
    return data


def _opt_str(value: Any) -> str | None:
    return None if value in (None, "") else str(value)


def _time(value: Any) -> str | None:
    try:
        return parse_platform_time(value)
    except ValueError as e:
        raise ParseError(str(e)) from e


def _successes(data: dict) -> tuple[list[FetchSuccess], list[FetchFailure]]:
    success: list[FetchSuccess] = []
    failures: list[FetchFailure] = []
    for item in data.get("success_list") or []:
        nos = order_nos(item)
        tracking_no = item.get("tracking_no")
        if not tracking_no:
            # 解析残缺不能吞掉订单：转成失败项，让上层走查回而不是当成已成功
            failures.append(FetchFailure(nos, "取号响应缺少运单号"))
            continue
        success.append(FetchSuccess(
            order_nos=nos,
            courier_code=str(item.get("logistics_company_code") or ""),
            tracking_no=str(tracking_no),
            template_code=_opt_str(item.get("logistics_template_code")),
            print_data=_opt_str(item.get("print_data")),
            sign=_opt_str(item.get("sign")),
        ))
    return success, failures


def _failures(data: dict, keys: tuple[str, ...]) -> list[FetchFailure]:
    out: list[FetchFailure] = []
    for key in keys:
        for item in data.get(key) or []:
            if isinstance(item, dict):
                out.append(FetchFailure(order_nos(item), str(item.get("fail_msg") or "")))
    return out


def parse_fetch_result(resp: dict) -> FetchResult:
    data = _data(resp)
    success, failures = _successes(data)
    failures += _failures(data, ("fail_orders_list", "fail_list"))
    return FetchResult(tuple(success), tuple(failures))


def parse_fetch_and_ship_result(resp: dict) -> FetchResult:
    data = _data(resp)
    success = [
        FetchSuccess(
            order_nos=order_nos(item),
            courier_code=str(item.get("logistics_company_code") or ""),
            tracking_no=str(item["tracking_no"]),
            template_code=_opt_str(item.get("logistics_template_code")),
            print_data=_opt_str(item.get("print_data")),
            sign=_opt_str(item.get("sign")),
        )
        for item in data.get("success_deliver_list") or []
        if item.get("tracking_no")
    ]
    failures = _failures(data, ("fail_orders_list", "fail_deliver_list"))
    return FetchResult(tuple(success), tuple(failures))


def parse_cancel_result(resp: dict) -> CancelResult:
    data = _data(resp)
    success = tuple(
        CancelSuccess(str(item.get("logistics_company_code") or ""), str(item["tracking_no"]))
        for item in data.get("success_list") or []
        if item.get("tracking_no")
    )
    failures = tuple(
        CancelFailure(
            _opt_str(item.get("logistics_company_code")),
            _opt_str(item.get("tracking_no")),
            str(item.get("fail_msg") or ""),
        )
        for item in data.get("fail_list") or []
        if isinstance(item, dict)
    )
    return CancelResult(success, failures, _opt_str(data.get("fail_msg")))


def parse_product_types(resp: dict) -> ProductTypes:
    data = _data(resp)
    products = data.get("logistics_product") or []
    exp_type = products[0].get("selectedValue") if products else None
    added = data.get("added_services")
    return ProductTypes(_opt_str(exp_type), tuple(added if isinstance(added, list) else []))


def parse_receiver(resp: dict) -> ReceiverInfo:
    data = _data(resp)
    info = data.get("receive_info")
    if not isinstance(info, dict) or not info:
        raise ParseError("响应缺少 data.receive_info")
    addr = info.get("post_addr") or {}
    region = "".join(
        (addr.get(k) or {}).get("name") or "" for k in ("province", "city", "town", "street")
    ) or None
    return ReceiverInfo(
        name=_opt_str(info.get("post_receiver")),
        phone=_opt_str(info.get("post_tel")),
        region=region,
        detail=_opt_str(addr.get("detail")),
        expire_at=_time(info.get("expire_time")),
        verify_type=_opt_str(data.get("verify_type")),
    )


def parse_logistics_tracking(resp: dict) -> str | None:
    """取号超时恢复：`data.logistics[].logistics_code` 即运单号（backend 5.5 / gaps API-19）。"""
    data = _data(resp)
    for item in data.get("logistics") or []:
        code = item.get("logistics_code") or item.get("tracking_no") or item.get("waybill_no")
        if code:
            return str(code)
    for pkg in data.get("logistics_list") or []:
        for key in ("logistics_code", "tracking_no", "waybill_no", "track_no"):
            if pkg.get(key):
                return str(pkg[key])
        for item in pkg.get("logistics") or []:
            code = item.get("logistics_code") or item.get("tracking_no")
            if code:
                return str(code)
    return None
