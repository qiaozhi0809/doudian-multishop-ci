"""分页列表的排序参数：`sort=<字段>&order=asc|desc`。

字段是白名单（Literal，非白名单 422），与 store 层各列表的排序映射一一对应
（tests/api/list_sort_test.py 校验两边一致）。省略 sort 时用列表自己的默认排序。
"""

from typing import Literal

# 飞鸽会话列表不在 SQL 里排和筛：白名单与规则一起定义在 domain，这里只转出
from app.domain.im_view_rules import ImConversationSort as ImConversationSort
from app.domain.im_view_rules import ImQuick as ImQuick

SortOrder = Literal["asc", "desc"]

OrderSort = Literal[
    "shop_name", "platform_status", "status", "amount_cents", "pay_time", "exp_ship_time"
]
LabelPoolSort = Literal["shop_name", "status", "amount_cents", "pay_time"]
AftersaleSort = Literal[
    "shop_name", "type", "status", "refund_amount_cents", "apply_time", "status_deadline"
]
ProductSort = Literal["shop_name", "tab", "price", "stock_num", "sell_num", "sell_num_30d"]
StockSort = Literal[
    "shop_name", "total_stock_num", "spot_stock_num", "future_stock_num",
    "total_occupied_stock_num", "total_unoccupied_stock_num", "status", "synced_at",
]
UnsettledSort = Literal[
    "shop_name", "income_amount_cents", "platform_service_fee_cents",
    "unsettled_amount_cents", "ecom_order_status", "synced_at",
]
FindingSort = Literal["shop_name", "kind", "created_at", "status"]

# 计数卡快捷筛选（`quick=<键>`）：键名与各计数接口的字段同名，非白名单 422；在 SQL 里筛完再分页。
OrderQuick = Literal["stock_up", "exp_ship", "ship_delay", "in_aftersale"]
ProductQuick = Literal["onsale", "draft", "audit", "sell_out_new", "unpass", "forbidden"]
AftersaleQuick = Literal["pending", "audit", "due_soon"]
StockQuick = Literal["alarm", "sold_out"]
