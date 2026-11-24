"""抖店客户端异常分类（backend 5.2）。业务层只按类型处理。"""


class DoudianError(Exception):
    """所有抖店适配层异常的基类。"""


class SessionExpired(DoudianError):
    """会话失效（code=10008）。"""


class BizRejected(DoudianError):
    """业务拒绝：不重试。"""

    def __init__(self, code: str, msg: str) -> None:
        super().__init__(f"{code}: {msg}")
        self.code = code
        self.msg = msg


class RiskBlocked(DoudianError):
    """触发风控：暂停该店自动化，人工检查。"""

    def __init__(self, code: str, msg: str) -> None:
        super().__init__(f"{code}: {msg}")
        self.code = code
        self.msg = msg


class TransientError(DoudianError):
    """超时 / 5xx / 限流：只读接口可退避重试。"""


class EgressUnavailable(TransientError):
    """该店出口（代理）不可用：不重试，更不得改走直连。"""


class ParseError(DoudianError):
    """响应结构不符合预期。"""
