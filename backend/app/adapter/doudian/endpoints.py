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

BASE_URL = "https://fxg.jinritemai.com"
APPID = 1
AID = 4272

SEARCHLIST_MAX_PAGE_SIZE = 200


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
SEARCHLIST = Endpoint("searchlist", "GET", "/api/order/searchlist", bid.ORDER, page_base=0)
EXPRESS_LIST = Endpoint(
    "express_list", "POST", "/api/order/expressList", bid.ORDER, body="json", common_in="query"
)
ADDRESS_LIST = Endpoint(
    "address_list", "GET", "/shopuser/tshopuser/getAfterSaleList", bid.ORDER, page_base=1,
    fixed_params={"keyword": "", "pageSize": 500, "sort": 2, "source": "send_deliver"},
)
TEMPLATE_LIST = Endpoint("template_list", "GET", "/shopuser/power/searchTemplates", bid.ORDER)
EBILL_ACCOUNTS = Endpoint(
    "ebill_accounts", "GET", "/shopuser/power/getEbillAccountListByExpress", bid.ORDER
)
