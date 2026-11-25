"""资金接口响应 → DTO（docs/api/fund.md 附录 F）。

账单金额字段尚待校准（F.4）：命中候选字段即按约定换算，全部未命中记 0 并标记 pending，
不得用猜测值冒充事实。
"""

from decimal import Decimal, InvalidOperation
from typing import Any

from app.adapter.doudian.errors import ParseError
from app.adapter.doudian.parse_fields import (
    json_object,
    list_with_total,
    opt_int,
    opt_str,
    require_data,
    require_str,
)
from app.domain.aggregate_models import (
    BILL_AMOUNT_CONFIRMED,
    BILL_AMOUNT_PENDING,
    BillItemDTO,
    FundUnsettledDTO,
    MarginDTO,
)
from app.domain.money import yuan_to_cents

CONFIRMED_AMOUNT_FIELD = "amount_cents"
# F.4 候选：整数按分、带小数点按元
CANDIDATE_AMOUNT_FIELDS = (
    "amount", "bill_amount", "order_amount", "settle_amount", "settlement_amount",
    "total_amount", "charge_amount", "fee",
)


def parse_unsettled(resp: dict) -> tuple[list[FundUnsettledDTO], int, int | None]:
    """待结算订单：`data` 每项是 JSON 字符串（F.1b），需二次解析。"""
    data = require_data(resp)
    if not isinstance(data, list):
        raise ParseError("待结算列表的 data 不是数组")
    out: list[FundUnsettledDTO] = []
    for entry in data:
        row = json_object(entry, "待结算条目")
        out.append(FundUnsettledDTO(
            shop_order_no=require_str(row, "shop_order_no", "待结算条目"),
            sku_order_no=require_str(row, "sku_order_no", "待结算条目"),
            product_id=opt_str(row.get("product_id")),
            income_amount_cents=opt_int(row.get("income_amount")),
            unsettled_amount_cents=opt_int(row.get("unsettled_amount")),
            platform_service_fee_cents=opt_int(row.get("platform_service_fee")),
            ecom_order_status=opt_str(row.get("ecom_order_status")),
            expected_settle_time=opt_str(row.get("expected_settle_time")),
            settle_period_detail=opt_str(row.get("settle_period_detail")),
            raw=row,
        ))
    total = opt_int(resp.get("total"))
    aggregation = resp.get("aggregation_res")
    total_cents = None
    if isinstance(aggregation, dict):
        total_cents = opt_int(aggregation.get("total_unsettled_amount"))
    return out, len(out) if total is None else total, total_cents


def _cents_from(value: Any) -> int | None:
    """整数（含数字字符串）按分；带小数点按元（F.4）。无法识别返回 None。"""
    exact = opt_int(value)
    if exact is not None:
        return exact
    try:
        return yuan_to_cents(Decimal(str(value).strip()))
    except (InvalidOperation, ValueError):
        return None


def bill_amount(item: dict) -> tuple[int, str, str | None]:
    """(金额分, 校准状态, 命中的字段名)。"""
    if item.get(CONFIRMED_AMOUNT_FIELD) not in (None, ""):
        amount = _cents_from(item[CONFIRMED_AMOUNT_FIELD])
        if amount is not None:
            return amount, BILL_AMOUNT_CONFIRMED, CONFIRMED_AMOUNT_FIELD
    for field in CANDIDATE_AMOUNT_FIELDS:
        if item.get(field) in (None, ""):
            continue
        amount = _cents_from(item[field])
        if amount is not None:
            return amount, BILL_AMOUNT_CONFIRMED, field
    return 0, BILL_AMOUNT_PENDING, None


def parse_bills(resp: dict) -> tuple[list[BillItemDTO], int]:
    rows, total = list_with_total(resp)
    out = []
    for row in rows:
        amount, status, field = bill_amount(row)
        out.append(BillItemDTO(amount_cents=amount, amount_status=status,
                               amount_field=field, raw=row))
    return out, total


def parse_margin(resp: dict) -> MarginDTO:
    data = require_data(resp)
    if not isinstance(data, dict):
        raise ParseError("保证金信息的 data 不是对象")
    withdraw = data.get("withdraw_detail")
    risk = data.get("risk_detail")
    withdraw = withdraw if isinstance(withdraw, dict) else {}
    risk = risk if isinstance(risk, dict) else {}
    return MarginDTO(
        payable_cents=opt_int(data.get("payable")),
        balance_cents=opt_int(data.get("balance")),
        basic_payable_cents=opt_int(risk.get("basic_payable")),
        basic_balance_cents=opt_int(risk.get("basic_balance")),
        withdrawable_cents=opt_int(withdraw.get("withdrawable_amount")),
        level=opt_str(data.get("level")),
        raw=data,
    )


def unsettled_display(raw: dict) -> dict[str, Any]:
    """待结算条目的展示选摘（表里没有名称列，从 raw_json 读取）。"""
    return {
        "product_name": opt_str(raw.get("product_name")),
        "sku_detail_text": opt_str(raw.get("sku_detail_text")),
        "collection_subject_name": opt_str(raw.get("collection_subject_name")),
        "settlement_delay_days": _delay_days(raw.get("settle_period_detail")),
    }


def _delay_days(value: Any) -> int | None:
    """延迟天数从平台的 `settle_period_detail` 读取，不写死（engineering-rules 5.2）。"""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = json_object(value, "settle_period_detail")
    except ParseError:
        return None
    return opt_int(parsed.get("delay_day"))
