"""取号结果不明时的查回恢复（backend 5.5、backend 5.12、gaps API-19）。

平台拒绝为已取号订单再次取号，因此超时 / 「不存在可取号商品」时不能重试，
只能通过 `getOrderLogistics` 查该订单当前的运单号。该接口对「已取号未发货」
订单是否返回运单号尚未实测（API-19），查不到时由调用方保持待核实。
"""

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.label_parsers import parse_logistics_tracking


async def find_tracking_no(client: FxgClient, order_no: str) -> str | None:
    resp = await client.call(ep.ORDER_LOGISTICS, params={"order_id": order_no})
    return parse_logistics_tracking(resp)
