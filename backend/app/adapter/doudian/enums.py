"""抖店接口枚举参数（engineering-rules 5.1）。"""

from enum import StrEnum


class BillQueryType(StrEnum):
    """资金 `query_item` 的 query_type（docs/api/fund.md F.1 / F.1b）。"""

    CHARGE_BILL_ITEM = "CHARGE_BILL_ITEM"  # 已出账账单
    SHOP_UNSETTLED_ORDER = "SHOP_UNSETTLED_ORDER"  # 待结算订单


class BillTimeType(StrEnum):
    BILL_TIME = "BILL_TIME"
