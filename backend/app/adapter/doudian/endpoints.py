"""抖店接口注册表：路径、参数、分页基准、通道逐接口声明（engineering-rules 8.5）。

参数位置：body="query" 的接口，公共参数、固定参数与调用参数都在 URL 查询串；
body="json" / "form" 的接口，固定参数并入请求体，`params` 进查询串，公共参数按 `common_in`
放请求体（默认）或 URL 查询串（如 expressList）。
新增接口前必须先在 docs/api/ 记录实测结果。
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from app.adapter.doudian import bid
from app.domain.order_status import OrderTab

BASE_URL = "https://fxg.jinritemai.com"
APPID = 1
AID = 4272

SEARCHLIST_MAX_PAGE_SIZE = 200
SEARCHLIST_PAGE_BASE = 0
ADDRESS_PAGE_SIZE = 500


@dataclass(frozen=True)
class Endpoint:
    name: str
    method: Literal["GET", "POST"]
    path: str
    bid: str
    body: Literal["query", "json", "form"] = "query"
    fixed_params: Mapping[str, str | int] = field(default_factory=dict)
    page_base: int | None = None
    write: bool = False
    channel: Literal["protocol", "browser"] = "protocol"
    common_in: Literal["query", "body"] = "body"  # 仅 json / form 接口使用


TABCNT = Endpoint(
    "tabcnt", "GET", "/api/order/tabcnt", bid.ORDER,
    fixed_params={"tabcnt_version": "v1", "tab": "all"},
)
SEARCHLIST = Endpoint(
    "searchlist", "GET", "/api/order/searchlist", bid.ORDER, page_base=SEARCHLIST_PAGE_BASE
)
EXPRESS_LIST = Endpoint(
    "express_list", "POST", "/api/order/expressList", bid.ORDER, body="json", common_in="query"
)
ADDRESS_LIST = Endpoint(
    "address_list", "GET", "/shopuser/tshopuser/getAfterSaleList", bid.ORDER, page_base=1,
    fixed_params={
        "keyword": "", "pageSize": ADDRESS_PAGE_SIZE, "sort": 2, "source": "send_deliver",
    },
)
TEMPLATE_LIST = Endpoint("template_list", "GET", "/shopuser/power/searchTemplates", bid.ORDER)
EBILL_ACCOUNTS = Endpoint(
    "ebill_accounts", "GET", "/shopuser/power/getEbillAccountListByExpress", bid.ORDER
)

# ---- M2 取号 / 作废 / 解密（docs/api/write.md A.2.2 / A.2.5 / A.2.6、read.md A.1）----
# 写接口 write=True：客户端不自动重试；结果不明时由 service 走「待核实 → 查回」。
LABEL_FETCH = Endpoint(
    "label_fetch", "POST", "/api/order/batchFetchTrackingNos", bid.ORDER, body="json", write=True
)
LABEL_FETCH_AND_SHIP = Endpoint(
    "label_fetch_and_ship", "POST", "/api/order/batchFetchTrackingNosAndDeliverGoods",
    bid.ORDER, body="json", write=True,
)
CANCEL_TRACKING_NOS = Endpoint(
    "cancel_tracking_nos", "POST", "/api/order/batchCancelTrackingNos",
    bid.ORDER, body="json", write=True,
)
# 查询型 POST：只读语义，允许退避重试
PRODUCT_TYPES = Endpoint(
    "product_types", "POST", "/api/order/query_added_services_and_product_types",
    bid.ORDER, body="json",
)
RECEIVE_INFO = Endpoint("receive_info", "GET", "/api/order/receiveinfo", bid.ORDER)
ORDER_LOGISTICS = Endpoint("order_logistics", "GET", "/api/order/getOrderLogistics", bid.ORDER)

# ---- M3 打印：补打面单数据（docs/design/flows.md 第 10 节）----
# 查询型 POST：只读语义，允许退避重试；返回结构尚未实测，
# 解析容错见 adapter/doudian/print_parsers.py
BATCH_GET_PRINT_INFOS = Endpoint(
    "batch_get_print_infos", "POST", "/shopuser/olSend/batchGetPrintInfos",
    bid.ORDER, body="json",
)


# ---- searchlist 的两种查询参数 ----
# tab 与 order_status 必须同时传；全部订单时 order_status 为空串（docs/api/read.md）

def searchlist_pending_params(page: int) -> dict[str, str | int]:
    """待发货订单：整页 200 条。"""
    return {
        "tab": OrderTab.STOCK_UP.value, "order_status": OrderTab.STOCK_UP.value, "scene": 1,
        "page": page, "pageSize": SEARCHLIST_MAX_PAGE_SIZE,
    }


def searchlist_by_order_id_params(order_no: str) -> dict[str, str | int]:
    """按订单号补查任意状态的订单。"""
    return {
        "tab": OrderTab.ALL.value, "order_status": "", "order_id": order_no,
        "page": SEARCHLIST_PAGE_BASE, "pageSize": 10,
    }
