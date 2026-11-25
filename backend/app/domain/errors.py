"""跨层共用的业务异常。"""


class NotFound(Exception):
    """请求的资源（店铺、账号等）不存在。

    不继承 LookupError：KeyError / IndexError 是 LookupError 的子类，
    代码缺陷不能被伪装成「不存在」。
    """

    def __init__(self, message: str, shop_id: int | None = None) -> None:
        super().__init__(message)
        self.shop_id = shop_id


class InvalidRequest(Exception):
    """请求内容不合法（字段取值、格式），对应 422。"""


class DryRunBlocked(Exception):
    """演练模式：拒绝发出任何写请求（engineering-rules 8.3）。"""


class DecryptCooldown(Exception):
    """该店解密处于冷却期（602502151），只暂停解密、不暂停取号（flows 7.3）。"""

    def __init__(
        self, message: str = "该店解密冷却中，请约 3 小时后再试", shop_id: int | None = None
    ):
        super().__init__(message)
        self.shop_id = shop_id
