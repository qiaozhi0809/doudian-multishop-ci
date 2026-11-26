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


def test_scan_job_passes_use_cloak_and_proxy_to_scanner(tmp_path):
    """接线行为测试：use_cloak 与店铺代理必须真的到达扫码函数，不能只靠签名检查。"""
    import asyncio

    from app.adapter.browser.login import LoginResult

    calls: list[dict] = []

    async def fake_scan(profile, channel, proxy, timeout_s, use_cloak=False, registry=None):
        calls.append({"proxy": proxy, "use_cloak": use_cloak})
        return LoginResult(
            cookies=[], token="tok", expires_at="2030-01-01T00:00:00Z", device_headers={},
        )

    class FakeRunner:
        def proxy_for(self, shop_id):
            return "http://user:pass@1.2.3.4:8080"

    class FakeSessions:
        def save_login(self, shop_id, result):
            pass

    flow = ShopLoginFlow(
        FakeRunner(), FakeSessions(), None, None, tmp_path, "chrome",
        scan=fake_scan, use_cloak=True,
    )
    asyncio.run(flow._scan_job(1)(None))

    assert len(calls) == 1
    assert calls[0]["use_cloak"] is True
    assert calls[0]["proxy"] == "http://user:pass@1.2.3.4:8080"


def _run_scan_job(tmp_path, calls: list, **flow_kwargs) -> None:
    """跑一次扫码任务体，把扫码与保存会话按发生顺序记进 calls。"""
    import asyncio

    from app.adapter.browser.login import LoginResult

    async def fake_scan(profile, channel, proxy, timeout_s, use_cloak=False, registry=None):
        calls.append("scan")
        return LoginResult(
            cookies=[], token="tok", expires_at="2030-01-01T00:00:00Z", device_headers={},
        )

    class FakeRunner:
        def proxy_for(self, shop_id):
            return "http://p:1"

    class FakeSessions:
        def save_login(self, shop_id, result):
            calls.append("save")

    flow = ShopLoginFlow(
        FakeRunner(), FakeSessions(), None, None, tmp_path, "chrome",
        scan=fake_scan, **flow_kwargs,
    )
    asyncio.run(flow._scan_job(7)(None))


def test_scan_yields_im_profile_before_browser(tmp_path):
    calls: list = []
    yielded: list[int] = []

    async def fake_yield(shop_id):
        calls.append("yield")
        yielded.append(shop_id)
        return True

    _run_scan_job(tmp_path, calls, yield_profile=fake_yield)

    assert calls == ["yield", "scan", "save"]
    assert yielded == [7]


def test_scan_without_hook_unchanged(tmp_path):
    calls: list = []

    _run_scan_job(tmp_path, calls, yield_profile=None)

    assert calls == ["scan", "save"]
