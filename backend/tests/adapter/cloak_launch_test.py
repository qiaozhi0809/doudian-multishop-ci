"""CloakBrowser 启动参数构造：不真正启动浏览器，只验证参数形态。"""

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
