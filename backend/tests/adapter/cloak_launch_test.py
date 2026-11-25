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
