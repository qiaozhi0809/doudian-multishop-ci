"""ShopLoginFlow 把 use_cloak 透传给 scan_login。"""

import inspect

from app.service.shop_login import ShopLoginFlow


def test_flow_accepts_use_cloak_flag():
    params = inspect.signature(ShopLoginFlow.__init__).parameters

    assert "use_cloak" in params
    assert params["use_cloak"].default is False


def test_cloak_unavailable_is_user_facing():
    """CloakBrowser 不可用的提示必须能出现在用户可见的错误里，否则安装提示被吞成「登录失败」。"""
    from app.adapter.browser.login import CloakUnavailable
    from app.service.shop_login import _USER_FACING

    assert CloakUnavailable in _USER_FACING
