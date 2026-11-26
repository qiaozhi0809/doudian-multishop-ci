"""CloakBrowser 启动参数构造：不真正启动浏览器，只验证参数形态。"""

import asyncio
import sys
import types

import pytest

from app.adapter.browser import cloak_launch
from app.adapter.browser.cloak_launch import BINARY_MISSING, CloakUnavailable
from app.adapter.browser.login import build_cloak_kwargs
from app.shared.cloak import SEED_MAX, SEED_MIN


def test_build_cloak_kwargs_carries_fingerprint(tmp_path):
    kwargs = build_cloak_kwargs(tmp_path, None)

    assert kwargs["user_data_dir"] == str(tmp_path)
    assert kwargs["headless"] is False
    assert kwargs["proxy"] is None
    seed_arg = kwargs["args"][0]
    assert seed_arg.startswith("--fingerprint=")
    assert SEED_MIN <= int(seed_arg.split("=")[1]) <= SEED_MAX


def test_build_cloak_kwargs_passes_proxy_dict_through(tmp_path):
    proxy = {"server": "http://1.2.3.4:8080", "username": "u", "password": "p"}

    kwargs = build_cloak_kwargs(tmp_path, proxy)

    assert kwargs["proxy"] == proxy


def test_build_cloak_kwargs_is_stable_across_calls(tmp_path):
    first = build_cloak_kwargs(tmp_path, None)["args"]
    second = build_cloak_kwargs(tmp_path, None)["args"]

    assert first == second


def test_scan_login_reports_missing_package(monkeypatch, tmp_path):
    """cloakbrowser 未安装时必须给出可执行的提示，而不是裸 ImportError。"""
    import asyncio
    import sys

    import pytest

    import app.adapter.browser.login as login_mod

    monkeypatch.setitem(sys.modules, "cloakbrowser", None)

    with pytest.raises(RuntimeError, match="cloakbrowser"):
        asyncio.run(login_mod.scan_login(tmp_path, "chrome", None, use_cloak=True))


def test_scan_login_cloak_branch_passes_proxy_and_seed(monkeypatch, tmp_path):
    """cloak 分支必须把代理 dict 与固定 seed 传进启动参数，且用完关闭上下文。"""
    import asyncio
    import sys
    import types

    import app.adapter.browser.login as login_mod

    captured: dict = {}

    class FakeCtx:
        pages: list = []

        async def new_page(self):
            return object()

        async def close(self):
            captured["closed"] = True

    async def fake_launch(**kwargs):
        captured.update(kwargs)
        return FakeCtx()

    fake_module = types.ModuleType("cloakbrowser")
    fake_module.launch_persistent_context_async = fake_launch
    monkeypatch.setitem(sys.modules, "cloakbrowser", fake_module)
    monkeypatch.setattr(cloak_launch, "binary_ready", lambda: True)

    async def fake_await_login(ctx, page, timeout_s):
        return "tok", {"User-Agent": "ua"}, [{"name": "sid_guard", "expires": 1893456000}]

    monkeypatch.setattr(login_mod, "await_login", fake_await_login)

    result = asyncio.run(
        login_mod.scan_login(tmp_path, "chrome", "http://user:pass@1.2.3.4:8080", use_cloak=True)
    )

    assert captured["user_data_dir"] == str(tmp_path)
    assert captured["proxy"] == {
        "server": "http://1.2.3.4:8080",
        "username": "user",
        "password": "pass",
    }
    assert captured["args"][0].startswith("--fingerprint=")
    assert captured["headless"] is False
    assert captured.get("closed") is True
    assert result.token == "tok"
    assert result.expires_at == "2030-01-01T00:00:00Z"


def test_build_cloak_kwargs_disables_default_viewport(tmp_path):
    """有头模式必须显式关掉视口：cloakbrowser 默认塞 1920x947 的写死视口，
    与真实窗口尺寸不一致时页面会被渲染成错误的缩放比例。"""
    kwargs = build_cloak_kwargs(tmp_path, None)

    assert kwargs["viewport"] is None


WEBRTC = "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"
PROXY = "http://user:secret-pw@203.0.113.5:8000"


class _Page:
    async def goto(self, *_a, **_k):
        raise RuntimeError("offline")  # 单页失败直接跳过，测试不用等渲染


class _Ctx:
    def __init__(self) -> None:
        self.pages = [_Page()]
        self.closed = False

    async def close(self):
        self.closed = True


def _fake_cloak(monkeypatch, *, ready=True, error: Exception | None = None) -> dict:
    captured: dict = {}

    async def fake_launch(*args, **kwargs):
        if args:
            kwargs["user_data_dir"] = args[0]
        captured.update(kwargs)
        if error is not None:
            raise error
        return _Ctx()

    mod = types.ModuleType("cloakbrowser")
    mod.launch_persistent_context_async = fake_launch
    monkeypatch.setitem(sys.modules, "cloakbrowser", mod)
    monkeypatch.setattr(cloak_launch, "binary_ready", lambda: ready)
    return captured


def _scan(tmp_path, proxy):
    import app.adapter.browser.login as login_mod

    return asyncio.run(login_mod.scan_login(tmp_path, "chrome", proxy, use_cloak=True))


def _scrape(tmp_path, proxy):
    from app.adapter.browser.scrape import scrape_platform_info

    return asyncio.run(scrape_platform_info(tmp_path, proxy))


@pytest.mark.parametrize("run", [_scan, _scrape])
def test_missing_binary_is_cloak_unavailable_without_launching(monkeypatch, tmp_path, run):
    """运行时绝不在事件循环里同步下载：二进制不在就直接报错，提示按部署文档预下载。"""
    captured = _fake_cloak(monkeypatch, ready=False)
    with pytest.raises(CloakUnavailable) as ei:
        run(tmp_path, PROXY)
    assert str(ei.value) == BINARY_MISSING
    assert captured == {}


@pytest.mark.parametrize("run", [_scan, _scrape])
@pytest.mark.parametrize("make_error", [
    lambda: FileNotFoundError(f"chrome --proxy-server={PROXY} not found"),
    lambda: __import__("playwright.async_api", fromlist=["Error"]).Error(
        f"launch failed: --proxy-server={PROXY}"),
])
def test_launch_failure_maps_to_cloak_unavailable_without_args(
    monkeypatch, tmp_path, run, make_error,
):
    _fake_cloak(monkeypatch, error=make_error())
    with pytest.raises(CloakUnavailable) as ei:
        run(tmp_path, PROXY)
    assert "secret-pw" not in str(ei.value) and "203.0.113.5" not in str(ei.value)
    assert ei.value.__cause__ is None and ei.value.__suppress_context__


@pytest.mark.parametrize("run", [_scan, _scrape])
def test_proxy_mode_blocks_non_proxied_webrtc(monkeypatch, tmp_path, run):
    captured = _fake_cloak(monkeypatch)
    try:
        run(tmp_path, PROXY)
    except Exception:  # noqa: BLE001 - 扫码会因为假页面失败，这里只看启动参数
        pass
    assert WEBRTC in captured["args"]


@pytest.mark.parametrize("run", [_scan, _scrape])
def test_direct_mode_has_no_webrtc_flag(monkeypatch, tmp_path, run):
    captured = _fake_cloak(monkeypatch)
    try:
        run(tmp_path, None)
    except Exception:  # noqa: BLE001 - 同上
        pass
    assert WEBRTC not in captured["args"]


def test_scrape_is_headful_offscreen_like_scan(monkeypatch, tmp_path):
    """同步收款信息与扫码同一套环境：有头、viewport 跟随真实窗口，窗口放到屏幕外。"""
    captured = _fake_cloak(monkeypatch)
    assert _scrape(tmp_path, PROXY) == {}
    assert captured["headless"] is False
    assert captured["viewport"] is None
    assert "--window-position=-32000,-32000" in captured["args"]
    assert captured["proxy"] == {
        "server": "http://203.0.113.5:8000", "username": "user", "password": "secret-pw",
    }
    scan_args = build_cloak_kwargs(tmp_path, {"server": "http://203.0.113.5:8000"})["args"]
    from app.shared.cloak import OFFSCREEN_RENDER, OFFSCREEN_WINDOW

    extra = {OFFSCREEN_WINDOW, *OFFSCREEN_RENDER}
    assert extra <= set(captured["args"])
    assert [a for a in captured["args"] if a not in extra] == scan_args


def test_binary_ready_checks_cache_and_override(monkeypatch, tmp_path):
    monkeypatch.delenv("CLOAKBROWSER_BINARY_PATH", raising=False)
    monkeypatch.setenv("CLOAKBROWSER_CACHE_DIR", str(tmp_path / "empty"))
    assert cloak_launch.binary_ready() is False
    exe = tmp_path / "chrome"
    exe.write_text("")
    monkeypatch.setenv("CLOAKBROWSER_BINARY_PATH", str(exe))
    assert cloak_launch.binary_ready() is True


@pytest.mark.parametrize("run", [_scan, _scrape])
@pytest.mark.parametrize(("make_error", "expected"), [
    (lambda: PermissionError(f"exec {PROXY}"), cloak_launch.BINARY_NOT_EXECUTABLE),
    (lambda: FileNotFoundError(f"chrome {PROXY}"), cloak_launch.BINARY_MISSING),
    (lambda: OSError(28, f"No space left {PROXY}"), cloak_launch.PROFILE_UNWRITABLE),
    (lambda: __import__("playwright.async_api", fromlist=["Error"]).Error(
        f"Failed to create a ProcessSingleton for your profile directory {PROXY}"),
     cloak_launch.PROFILE_IN_USE),
    (lambda: __import__("playwright.async_api", fromlist=["Error"]).Error(
        f"crashed {PROXY}"), cloak_launch.LAUNCH_FAILED),
])
def test_launch_failure_messages_are_specific(monkeypatch, tmp_path, run, make_error, expected):
    _fake_cloak(monkeypatch, error=make_error())
    with pytest.raises(CloakUnavailable) as ei:
        run(tmp_path, PROXY)
    assert str(ei.value) == expected
    assert "secret-pw" not in str(ei.value) and "203.0.113.5" not in str(ei.value)


@pytest.mark.parametrize("run", [_scan, _scrape])
def test_unwritable_profile_dir_is_cloak_unavailable(monkeypatch, tmp_path, run):
    captured = _fake_cloak(monkeypatch)

    def boom(_profile_dir):
        raise PermissionError("read-only")

    monkeypatch.setattr(cloak_launch, "get_or_create_seed", boom)
    with pytest.raises(CloakUnavailable) as ei:
        run(tmp_path, PROXY)
    assert str(ei.value) == cloak_launch.PROFILE_UNWRITABLE
    assert captured == {}


class _Cdp:
    def __init__(self, calls: list, fail: bool = False) -> None:
        self.calls, self.fail = calls, fail

    async def send(self, method, params=None):
        if self.fail:
            raise RuntimeError("cdp gone")
        self.calls.append((method, params))
        return {"windowId": 7} if method == "Browser.getWindowForTarget" else {}

    async def detach(self):
        self.calls.append(("detach", None))


class _CdpCtx(_Ctx):
    def __init__(self, calls: list, fail: bool = False) -> None:
        super().__init__()
        self._cdp = _Cdp(calls, fail)

    async def new_cdp_session(self, _page):
        return self._cdp


def _launch_with(monkeypatch, tmp_path, ctx, platform, *, offscreen):
    async def fake_launch(**_kwargs):
        return ctx

    mod = types.ModuleType("cloakbrowser")
    mod.launch_persistent_context_async = fake_launch
    monkeypatch.setitem(sys.modules, "cloakbrowser", mod)
    monkeypatch.setattr(cloak_launch, "binary_ready", lambda: True)
    monkeypatch.setattr(cloak_launch, "_platform", lambda: platform)
    return asyncio.run(cloak_launch.launch_cloak(tmp_path, None, offscreen=offscreen))


def test_offscreen_on_macos_minimizes_window(monkeypatch, tmp_path):
    calls: list = []
    ctx = _CdpCtx(calls)
    assert _launch_with(monkeypatch, tmp_path, ctx, "darwin", offscreen=True) is ctx
    assert calls == [
        ("Browser.getWindowForTarget", None),
        ("Browser.setWindowBounds", {"windowId": 7, "bounds": {"windowState": "minimized"}}),
        ("detach", None),
    ]


@pytest.mark.parametrize(("platform", "offscreen"), [("win32", True), ("darwin", False)])
def test_no_minimize_on_windows_or_visible_window(monkeypatch, tmp_path, platform, offscreen):
    calls: list = []
    _launch_with(monkeypatch, tmp_path, _CdpCtx(calls), platform, offscreen=offscreen)
    assert calls == []


def test_minimize_failure_still_returns_context(monkeypatch, tmp_path):
    ctx = _CdpCtx([], fail=True)
    assert _launch_with(monkeypatch, tmp_path, ctx, "darwin", offscreen=True) is ctx
