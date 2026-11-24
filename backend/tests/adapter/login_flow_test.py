"""await_login：用假的 context / page 模拟，不启动真浏览器。"""

import asyncio

import pytest

from app.adapter.browser.login import LoginCancelled, await_login

TOKEN = "tok_" + "x" * 8
URL = f"https://fxg.jinritemai.com/api/order/tabcnt?__token={TOKEN}"
HEADERS = {"user-agent": "UA/1", "sec-ch-ua": '"X";v="1"'}


class FakeRequest:
    def __init__(self, url: str = URL) -> None:
        self.url = url

    async def all_headers(self) -> dict:
        return HEADERS


class FakeCtx:
    def __init__(self, calls: list) -> None:
        self.calls = calls
        self.handlers: dict[str, list] = {}

    def on(self, event, handler) -> None:
        self.handlers.setdefault(event, []).append(handler)

    def emit(self, event, *args) -> None:
        for h in self.handlers.get(event, []):
            h(*args)

    async def cookies(self) -> list[dict]:
        self.calls.append("cookies")
        return [{"name": "sessionid", "value": "v"}]


class FakePage:
    def __init__(self, ctx: FakeCtx, *, on_goto=None, load_error=None, goto_error=None) -> None:
        self.ctx = ctx
        self.on_goto = on_goto
        self.load_error = load_error
        self.goto_error = goto_error
        self.load_args = None

    async def goto(self, url: str) -> None:
        self.ctx.calls.append("goto")
        if self.on_goto:
            self.on_goto(self.ctx)
        if self.goto_error:
            raise self.goto_error

    async def wait_for_load_state(self, state: str, timeout: int) -> None:
        self.ctx.calls.append("load_state")
        self.load_args = (state, timeout)
        if self.load_error:
            raise self.load_error


def _emit_login(ctx: FakeCtx) -> None:
    ctx.emit("request", FakeRequest())


async def test_waits_for_load_before_reading_cookies():
    calls: list = []
    ctx = FakeCtx(calls)
    page = FakePage(ctx, on_goto=_emit_login)
    token, headers, cookies = await await_login(ctx, page, 5)
    assert calls == ["goto", "load_state", "cookies"]
    assert page.load_args == ("load", 10_000)
    assert token == TOKEN and headers == {"User-Agent": "UA/1", "sec-ch-ua": '"X";v="1"'}
    assert cookies == [{"name": "sessionid", "value": "v"}]


async def test_load_timeout_is_ignored():
    ctx = FakeCtx([])
    page = FakePage(ctx, on_goto=_emit_login, load_error=TimeoutError("load"))
    _, _, cookies = await await_login(ctx, page, 5)
    assert cookies and ctx.calls[-1] == "cookies"


async def test_ignores_foreign_host_and_requests_without_token():
    ctx = FakeCtx([])

    def emit(c: FakeCtx) -> None:
        c.emit("request", FakeRequest(f"https://evil.example.com/x?__token={TOKEN}"))
        c.emit("request", FakeRequest("https://fxg.jinritemai.com/x"))

    page = FakePage(ctx, on_goto=emit)
    with pytest.raises(TimeoutError):
        await await_login(ctx, page, 0.05)


async def test_closing_window_cancels_immediately():
    ctx = FakeCtx([])
    page = FakePage(
        ctx, on_goto=lambda c: asyncio.get_running_loop().call_soon(c.emit, "close", c)
    )
    with pytest.raises(LoginCancelled) as ei:
        await asyncio.wait_for(await_login(ctx, page, 300), 2)
    assert "浏览器已关闭" in str(ei.value)


async def test_window_closed_during_goto_is_cancelled():
    ctx = FakeCtx([])

    def close_then_fail(c: FakeCtx) -> None:
        c.emit("close", c)

    page = FakePage(ctx, on_goto=close_then_fail, goto_error=RuntimeError("Target closed"))
    with pytest.raises(LoginCancelled):
        await await_login(ctx, page, 300)


async def test_goto_failure_without_close_propagates():
    ctx = FakeCtx([])
    page = FakePage(ctx, goto_error=RuntimeError("net::ERR"))
    with pytest.raises(RuntimeError):
        await await_login(ctx, page, 300)


async def test_timeout_raises_timeout_error():
    ctx = FakeCtx([])
    with pytest.raises(TimeoutError):
        await await_login(ctx, FakePage(ctx), 0.05)
