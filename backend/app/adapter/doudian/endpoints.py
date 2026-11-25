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
from app.adapter.doudian.enums import BillQueryType, BillTimeType
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


# ---- M5 只读聚合（docs/api/aftersale.md / catalog.md / fund.md）----
# 分页基准随接口声明（engineering-rules 8.5）：售后 / 库存 1-based；商品 / 资金 0-based。

AFTERSALE_PAGE_SIZE = 50
PRODUCT_PAGE_SIZE = 100
STOCK_PAGE_SIZE = 100
FUND_PAGE_SIZE = 50
PRODUCT_GROUP_PAGE_SIZE = 100

AFTERSALE_CONF_VERSION = "v13"
AFTERSALE_DETAIL_EXTRA = '{"detail_upgrade_hit":"new","proof_record_show":"new"}'

AFTERSALE_LIST = Endpoint(
    "aftersale_list", "POST", "/after_sale/pc/list", bid.AFTERSALE, body="json",
    common_in="query",  # 请求体保持附录 E.1 记录的原样：公共参数走查询串
    page_base=1,
)
AFTERSALE_COUNTS = Endpoint(
    "aftersale_counts", "GET", "/shopuser/aftersale/counts", bid.AFTERSALE,
    fixed_params={"aftersale_platform_source": "fxg"},
)
AFTERSALE_DETAIL = Endpoint(
    "aftersale_detail", "GET", "/v1/aftersale/pc/detail", bid.AFTERSALE,
    fixed_params={"extra": AFTERSALE_DETAIL_EXTRA, "aftersale_platform_source": "fxg"},
)

PRODUCT_LIST = Endpoint(
    "product_list", "GET", "/product/tproduct/list", bid.GOODS, page_base=0
)
PRODUCT_COUNTS = Endpoint(
    "product_counts", "GET", "/product/tproduct/aggsProductCount", bid.GOODS
)
PRODUCT_GROUPS = Endpoint(
    "product_groups", "GET", "/product/tproduct/getProductGroupList", bid.GOODS,
    fixed_params={"pageSize": PRODUCT_GROUP_PAGE_SIZE},
)

STOCK_LIST = Endpoint(
    "stock_list", "POST", "/stock/manage/list", bid.ORDER, body="json", page_base=1
)
STOCK_WAREHOUSES = Endpoint(
    "stock_warehouses", "GET", "/stock/index/warehouse_list", bid.ORDER
)

FUND_QUERY_ITEM = Endpoint(
    "fund_query_item", "POST", "/bill_center/domestic/shop/query_item", bid.BILL_CENTER,
    body="json", common_in="query",  # 请求体保持附录 F.1 / F.1b 记录的原样
    page_base=0,
)
MARGIN_PAYABLE = Endpoint(
    "margin_payable", "GET", "/governance/shop/tpledgecash/payable/info_v2", bid.BILL_CENTER,
    fixed_params={"marginPlatform": "fxg_pc", "base_margin_platform": "fxg_pc", "csrf": ""},
)


def aftersale_list_body(
    page: int, page_size: int = AFTERSALE_PAGE_SIZE, *, status: int | None = None,
    after_sale_type: int | None = None, keyword: str = "",
) -> dict:
    """附录 E.1 已验证的请求体；`order_by` 固定按处理截止时间升序（做待办队列）。"""
    return {
        "pageSize": page_size, "page": page, "order_by": ["status_deadline asc"],
        "conf_version": AFTERSALE_CONF_VERSION, "search_receiver": keyword,
        "after_sale_status": "" if status is None else status,
        "after_sale_type": "" if after_sale_type is None else after_sale_type,
        "order_flag": [], "order_logistics_state": [],
        "shop_hit_gray_info": {"list_v1": {"hit": True}},
    }


def aftersale_counts_params(fields: str) -> dict[str, str]:
    return {"fields": fields}


def aftersale_detail_params(after_sale_id: str) -> dict[str, str]:
    return {"after_sale_id": after_sale_id}


def product_list_params(
    page: int, page_size: int = PRODUCT_PAGE_SIZE, *, tab: str | None = None,
    group_id: str | None = None,
) -> dict[str, str | int]:
    params: dict[str, str | int] = {"page": page, "pageSize": page_size}
    if tab:
        params["tab"] = tab
    if group_id:
        params["group_id"] = group_id
    return params


def stock_list_body(page: int, page_size: int = STOCK_PAGE_SIZE) -> dict[str, int]:
    """附录 D.2 已验证的请求体（同时带 `pageSize` 与 `page_size`）。"""
    return {"page": page, "pageSize": page_size, "sort": 0, "page_size": page_size}


def fund_bills_body(
    start: str, end: str, page: int, size: int = FUND_PAGE_SIZE,
) -> dict[str, str | int]:
    return {
        "time_type": BillTimeType.BILL_TIME.value, "start_time": start, "end_time": end,
        "page": page, "size": size, "query_type": BillQueryType.CHARGE_BILL_ITEM.value,
    }


def fund_unsettled_body(page: int, size: int = FUND_PAGE_SIZE) -> dict[str, str | int]:
    """附录 F.1b：`data` 每项是 JSON 字符串，需二次解析。"""
    return {
        "time_field": "expected_settle_ts",
        "query_type": BillQueryType.SHOP_UNSETTLED_ORDER.value,
        "order_by": "ecom_order_create_ts", "order_type": "desc",
        "product_field": "product_id", "order_no_field": "shop_order_no",
        "member_id": "", "page": page, "size": size,
    }


def margin_params(biz_id: str) -> dict[str, str]:
    return {"bizId": biz_id}
