"""发货前检查 / 发货的响应解析（依据 docs/api/write.md A.2.3 / A.2.4 的实测样本）。"""

from app.adapter.doudian.errors import ParseError
from app.adapter.doudian.parse_fields import opt_str, order_nos, require_data
from app.domain.models import (
    DeliverResult,
    PackageFailure,
    PackageSuccess,
    SendCheckResult,
)


def _int(value: object) -> int:
    try:
        return int(value or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError) as e:
        raise ParseError(f"无法解析数量: {value!r}") from e


def parse_sendcheck_result(resp: dict) -> SendCheckResult:
    data = require_data(resp)
    if not isinstance(data, dict):
        raise ParseError("响应 data 不是对象")
    details = data.get("doubleCheckDetail") or []
    if not isinstance(details, list):
        raise ParseError("doubleCheckDetail 不是数组")
    no_aftersale = data.get("withOutAftersalShopOrders") or []
    holder = data.get("placeHolder")
    return SendCheckResult(
        total=_int(data.get("total")),
        double_check_num=_int(data.get("doubleCheckNum")),
        double_check_detail=tuple(d for d in details if isinstance(d, dict)),
        without_aftersale=tuple(str(x) for x in no_aftersale),
        place_holder=holder if isinstance(holder, dict) else None,
    )


def parse_deliver_result(resp: dict) -> DeliverResult:
    """按 package 维度解析成功 / 失败（write.md A.2.4 关键发现 3）。"""
    data = require_data(resp)
    if not isinstance(data, dict):
        raise ParseError("响应 data 不是对象")
    success: list[PackageSuccess] = []
    failures: list[PackageFailure] = []
    for item in data.get("success_package_list") or []:
        tracking_no = opt_str(item.get("tracking_no"))
        if not tracking_no:
            # 残缺的成功项不能吞掉：转成失败项，让上层按失败处理
            failures.append(PackageFailure(
                opt_str(item.get("logistics_company_code")), None,
                "发货响应缺少运单号", order_nos(item)))
            continue
        success.append(PackageSuccess(
            courier_code=str(item.get("logistics_company_code") or ""),
            tracking_no=tracking_no,
            order_nos=order_nos(item),
        ))
    for key in ("fail_package_list", "fail_list"):
        for item in data.get(key) or []:
            if isinstance(item, dict):
                failures.append(PackageFailure(
                    opt_str(item.get("logistics_company_code")),
                    opt_str(item.get("tracking_no")),
                    str(item.get("fail_msg") or ""),
                    order_nos(item),
                ))
    return DeliverResult(tuple(success), tuple(failures))
