"""订单状态枚举。三套枚举相互独立，禁止互相转换猜测（engineering-rules 8.4）。"""

from enum import IntEnum, StrEnum


class OrderTab(StrEnum):
    """searchlist 的筛选参数（字符串）。"""

    ALL = "all"
    UNPAID = "unpaid"
    STOCK_UP = "stock_up"
    ON_DELIVERY = "on_delivery"
    RECEIVED = "received"
    CLOSED = "closed"


class PlatformOrderStatus(IntEnum):
    """数据字段 order_status（数字）。仅列已确认的值，其余值调用方保留原始整数。"""

    SHIPPED = 3
    CLOSED = 4
    COMPLETED = 5


PLATFORM_FINAL_STATUSES: frozenset[int] = frozenset(int(s) for s in PlatformOrderStatus)


class LocalOrderStatus(StrEnum):
    """本地履约状态（data-model 6.1），不被平台数据覆盖。"""

    SYNCED = "synced"
    PENDING_LABEL = "pending_label"
    LABEL_OBTAINED = "label_obtained"
    PRINTED = "printed"
    SHIPPED = "shipped"
    CLOSED = "closed"
    EXCEPTION = "exception"
    CANCELLED = "cancelled"
