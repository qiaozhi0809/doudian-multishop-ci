"""写操作幂等键（backend 5.11）。

取号 / 一体按「店 + 订单 + 第几次取号」；作废按运单号。`seq` 用已作废面单数 + 1，
保证作废后的重新取号不会撞上旧键、直接拿到旧结果。
"""


def label_key(shop_id: int, order_no: str, seq: int) -> str:
    return f"label:{shop_id}:{order_no}:{seq}"


def void_key(shop_id: int, courier_code: str, waybill_no: str) -> str:
    return f"void:{shop_id}:{courier_code}:{waybill_no}"


def ship_key(shop_id: int, courier_code: str, tracking_no: str) -> str:
    """发货幂等键（backend 5.6）：平台不阻止重复发货，本地必须先查这个键。"""
    return f"ship:{shop_id}:{courier_code}:{tracking_no}"


def next_seq(voided_count: int) -> int:
    return voided_count + 1
