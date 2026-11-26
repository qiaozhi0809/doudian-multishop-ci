"""扫码登录与读页面都经浏览器登记表启动，用途分别为 login / scrape。"""

from contextlib import asynccontextmanager

import app.adapter.browser.login as login_mod
from app.adapter.browser.browser_registry import Purpose
from app.adapter.browser.scrape import scrape_platform_info


class FakePage:
    async def goto(self, *a, **kw):
        raise RuntimeError("offline")


class FakeCtx:
    pages = [FakePage()]


class RecordingRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    @asynccontextmanager
    async def _yield(self):
        yield FakeCtx()

    def open_cloak(self, profile_dir, purpose, proxy, *, offscreen=False, max_age_s=None,
                   on_close=None):
        self.calls.append((profile_dir, purpose, proxy, offscreen))
        self.max_age_s, self.on_close = max_age_s, on_close
        return self._yield()


async def test_scrape_registers_as_scrape_offscreen(tmp_path):
    reg = RecordingRegistry()
    assert await scrape_platform_info(tmp_path, "http://1.2.3.4:8080", registry=reg) == {}
    assert reg.calls == [(tmp_path, Purpose.SCRAPE, {"server": "http://1.2.3.4:8080"}, True)]


async def test_scan_login_registers_as_login(monkeypatch, tmp_path):
    reg = RecordingRegistry()

    async def fake_await_login(ctx, page, timeout_s):
        return "tok", {}, []

    monkeypatch.setattr(login_mod, "await_login", fake_await_login)
    result = await login_mod.scan_login(tmp_path, "chrome", None, use_cloak=True, registry=reg)
    assert result.token == "tok"
    assert reg.calls == [(tmp_path, Purpose.LOGIN, None, False)]


async def test_scan_login_max_age_follows_timeout(monkeypatch, tmp_path):
    from app.adapter.browser.browser_timing import login_max_age

    reg = RecordingRegistry()

    async def fake_await_login(ctx, page, timeout_s):
        return "tok", {}, []

    monkeypatch.setattr(login_mod, "await_login", fake_await_login)
    await login_mod.scan_login(tmp_path, "chrome", None, 3600, use_cloak=True, registry=reg)
    assert reg.max_age_s == login_max_age(3600)


async def test_scan_login_reports_why_system_closed_the_window(monkeypatch, tmp_path):
    import pytest

    reg = RecordingRegistry()

    async def closed_by_sweep(ctx, page, timeout_s):
        reg.on_close("expired")  # 登记表关闭并回调后，await_login 才看到关窗
        raise login_mod.LoginCancelled("浏览器已关闭，扫码登录取消")

    monkeypatch.setattr(login_mod, "await_login", closed_by_sweep)
    with pytest.raises(login_mod.LoginCancelled, match="打开太久"):
        await login_mod.scan_login(tmp_path, "chrome", None, use_cloak=True, registry=reg)


async def test_scan_login_user_closed_window_keeps_message(monkeypatch, tmp_path):
    import pytest

    reg = RecordingRegistry()

    async def user_closed(ctx, page, timeout_s):
        raise login_mod.LoginCancelled("浏览器已关闭，扫码登录取消")

    monkeypatch.setattr(login_mod, "await_login", user_closed)
    with pytest.raises(login_mod.LoginCancelled, match="浏览器已关闭"):
        await login_mod.scan_login(tmp_path, "chrome", None, use_cloak=True, registry=reg)
