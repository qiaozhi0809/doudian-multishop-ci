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

    def open_cloak(self, profile_dir, purpose, proxy, *, offscreen=False, max_age_s=None):
        self.calls.append((profile_dir, purpose, proxy, offscreen))
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
