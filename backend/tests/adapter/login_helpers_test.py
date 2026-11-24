from datetime import UTC, datetime

import pytest

from app.adapter.browser.login import (
    device_headers_from,
    extract_token,
    playwright_proxy,
    session_expiry,
)

NOW = datetime(2026, 11, 25, 0, 0, 0, tzinfo=UTC)


def test_playwright_proxy_http():
    assert playwright_proxy("http://u:p@h.example:8000") == {
        "server": "http://h.example:8000", "username": "u", "password": "p",
    }


def test_playwright_proxy_none_and_no_credentials():
    assert playwright_proxy(None) is None
    assert playwright_proxy("https://h.example:8443") == {"server": "https://h.example:8443"}


def test_playwright_proxy_decodes_percent_encoding():
    got = playwright_proxy("http://u%40x:p%3Aw@h.example:8000")
    assert got["username"] == "u@x" and got["password"] == "p:w"


def test_playwright_proxy_rejects_socks5_auth():
    with pytest.raises(ValueError) as ei:
        playwright_proxy("socks5://u:p@h.example:1080")
    assert "p@" not in str(ei.value) and "u:p" not in str(ei.value)


def test_playwright_proxy_rejects_other_schemes_and_missing_port():
    with pytest.raises(ValueError):
        playwright_proxy("ftp://h.example:21")
    with pytest.raises(ValueError):
        playwright_proxy("http://h.example")


def test_extract_token():
    tok = "tok_" + "x" * 8
    url = f"https://fxg.jinritemai.com/api/order/tabcnt?a=1&__token={tok}&b=2"
    assert extract_token(url) == tok
    assert extract_token("https://fxg.jinritemai.com/api/order/tabcnt?a=1") is None
    assert extract_token("https://fxg.jinritemai.com/x?__token=") is None


def test_session_expiry_from_sid_guard():
    cookies = [
        {"name": "other", "value": "v", "expires": 1.0},
        {"name": "sid_guard", "value": "v", "expires": 1796000000.5},
    ]
    assert session_expiry(cookies, NOW) == "2026-11-30T00:53:20Z"


def test_session_expiry_fallback_60_days():
    expected = "2027-01-24T00:00:00Z"
    assert session_expiry([], NOW) == expected
    assert session_expiry([{"name": "sid_guard", "value": "v"}], NOW) == expected
    assert session_expiry([{"name": "sid_guard", "value": "v", "expires": -1}], NOW) == expected


def test_device_headers_from_picks_four_headers_case_insensitive():
    raw = {
        "user-agent": "UA/1", "sec-ch-ua": '"X";v="1"', "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"', "cookie": "should-not-copy", "accept": "*/*",
    }
    assert device_headers_from(raw) == {
        "User-Agent": "UA/1", "sec-ch-ua": '"X";v="1"', "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    }
    assert device_headers_from({"User-Agent": "UA/2"}) == {"User-Agent": "UA/2"}
