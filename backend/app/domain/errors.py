"""跨层共用的业务异常。"""


class NotFound(Exception):
    """请求的资源（店铺、账号等）不存在。

    不继承 LookupError：KeyError / IndexError 是 LookupError 的子类，
    代码缺陷不能被伪装成「不存在」。
    """

    def __init__(self, message: str, shop_id: int | None = None) -> None:
        super().__init__(message)
        self.shop_id = shop_id
