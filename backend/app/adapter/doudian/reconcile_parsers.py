"""订单事实（searchlist tab=all）→ `OrderFactDTO`（dashboard.md 3.1 / 附录 G.1）。

字段依据脱敏样本 backend/tests/fixtures/doudian/searchlist.json；缺失字段保持 None，不猜测。
"""

from typing import Any

from app.adapter.doudian.errors import ParseError
from app.adapter.doudian.parse_fields import opt_int, opt_str, platform_time, require_data
from app.domain.models import OrderFactDTO
from app.shared.time_bj import to_biz_date


def _data_list(resp: dict) -> list[dict]:
    data = require_data(resp)
    if not isinstance(data, list):
        raise ParseError("响应 data 不是数组")
    return [o for o in data if isinstance(o, dict)]


def _fact(o: dict) -> OrderFactDTO:
    order_no = o.get("shop_order_id")
    if order_no in (None, ""):
        raise ParseError("订单缺少 shop_order_id")
    pay_time = platform_time(o.get("pay_time"))
    logistic: Any = o.get("latest_logistic_info") or {}
    if not isinstance(logistic, dict):
        logistic = {}
    return OrderFactDTO(
        order_no=str(order_no),
        platform_status=opt_int(o.get("order_status")),
        user_id=opt_str(o.get("user_id")),
        create_time=platform_time(o.get("create_time")),
        pay_time=pay_time,
        biz_date=to_biz_date(pay_time) if pay_time else None,
        pay_amount_cents=opt_int(o.get("pay_amount")),
        goods_amount_cents=opt_int(o.get("total_goods_amount")),
        promotion_cents=opt_int(o.get("promotion_amount")),
        post_cents=opt_int(o.get("post_amount")),
        receive_amount_cents=opt_int(o.get("actual_receive_amount_int")),
        exp_ship_time=platform_time(o.get("exp_ship_time")),
        ship_time=platform_time(o.get("ship_time") or o.get("logistics_time")),
        tracking_no=opt_str(logistic.get("tracking_no")),
        company_code=opt_str(logistic.get("company_code")),
        raw=o,
    )


def parse_order_facts(resp: dict) -> list[OrderFactDTO]:
    return [_fact(o) for o in _data_list(resp)]
