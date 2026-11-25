from datetime import UTC, datetime

import pytest

from app.domain.egress_rules import (
    display_proxy,
    expiry_state,
    join_proxy_url,
    judge_egress,
    parse_provider_line,
    proxy_identity,
    split_proxy_url,
    validate_proxy_host,
    validate_proxy_url,
)

NOW = datetime(2026, 12, 1, 0, 0, 0, tzinfo=UTC)


def test_validate_accepts_http_and_https():
    assert validate_proxy_url("http://u:p@203.0.113.5:8000") == []
    assert validate_proxy_url("https://203.0.113.5:8443") == []


def test_validate_rejects_socks5():
    errors = validate_proxy_url("socks5://u:secret@203.0.113.5:1080")
    assert errors
    assert "secret" not in "".join(errors)


@pytest.mark.parametrize("url", ["ftp://203.0.113.5:21", "http://203.0.113.5", "http://:8000",
                                 "", "not a url", "http://203.0.113.5:99999"])
def test_validate_rejects_malformed(url):
    assert validate_proxy_url(url)


def test_parse_provider_line():
    line = "203.0.113.5|8000|u1|p1|2026-12-25"
    assert parse_provider_line(line) == ("http://u1:p1@203.0.113.5:8000", "2026-12-25")
    assert parse_provider_line(f"  {line}\n")[0] == "http://u1:p1@203.0.113.5:8000"


def test_parse_provider_line_encodes_special_chars():
    url, _ = parse_provider_line("203.0.113.5|8000|u@1|p:w/#|2026-12-25")
    assert url == "http://u%401:p%3Aw%2F%23@203.0.113.5:8000"
    assert validate_proxy_url(url) == []


@pytest.mark.parametrize("line", ["203.0.113.5|8000|u|p", "203.0.113.5|x|u|p|2026-12-25",
                                  "203.0.113.5|8000|u|topsecret|not-a-date", "||||"])
def test_parse_provider_line_rejects_bad_input_without_leaking(line):
    with pytest.raises(ValueError) as ei:
        parse_provider_line(line)
    assert "topsecret" not in str(ei.value)


def test_display_hides_credentials():
    assert display_proxy("http://u1:p1@203.0.113.5:8000") == "203.0.113.5:8000"
    assert "p1" not in display_proxy("http://u1:p1@203.0.113.5:8000")


def test_judge_egress_cases():
    assert judge_egress(None, "203.0.113.5", set()) == "ok"
    assert judge_egress("203.0.113.5", "203.0.113.5", {"203.0.113.9"}) == "ok"
    assert judge_egress("203.0.113.5", None, set()) == "unreachable"
    assert judge_egress(None, None, set()) == "unreachable"
    assert judge_egress("203.0.113.5", "203.0.113.6", set()) == "changed"
    assert judge_egress(None, "203.0.113.9", {"203.0.113.9"}) == "duplicate"
    assert judge_egress("203.0.113.5", "203.0.113.9", {"203.0.113.9"}) == "duplicate"


def test_expiry_state():
    assert expiry_state(None, NOW) == "ok"  # 未填写到期日视为不限
    assert expiry_state("2027-01-31", NOW) == "ok"
    assert expiry_state("2026-12-05", NOW) == "expiring"
    assert expiry_state("2026-12-07", NOW) == "expiring"  # 到期日当天整天有效（北京时间）
    assert expiry_state("2026-12-08", NOW) == "ok"
    assert expiry_state("2026-11-30", NOW) == "expired"
    assert expiry_state("2026-12-01T00:00:00Z", NOW) == "expired"
    assert expiry_state("2026-12-03T00:00:00Z", NOW) == "expiring"


# ---- 代理归一化（proxy-pool 1.1） ----

def test_identity_same_for_paste_and_url():
    pasted, _ = parse_provider_line("203.0.113.5|8000|u@x|p:w|2026-12-31")
    assert proxy_identity(pasted) == proxy_identity("http://u%40x:p%3Aw@203.0.113.5:8000")


def test_identity_ignores_host_case_and_differs_by_password():
    a = proxy_identity("http://u:p@Proxy.Example:8000")
    assert a == proxy_identity("http://u:p@proxy.example:8000")
    assert a != proxy_identity("http://u:q@proxy.example:8000")


def test_identity_is_sha256_hex_without_credentials():
    ident = proxy_identity("http://user-x:secret-y@203.0.113.5:8000")
    assert len(ident) == 64 and "secret-y" not in ident


def test_split_join_round_trip():
    url = "http://u%40x:p%3Aw@203.0.113.5:8000"
    parts = split_proxy_url(url)
    assert (parts.username, parts.password) == ("u@x", "p:w")
    assert (parts.scheme, parts.host, parts.port) == ("http", "203.0.113.5", 8000)
    assert join_proxy_url(parts) == url


def test_join_without_account_has_no_at():
    parts = split_proxy_url("https://203.0.113.5:8443")
    assert parts.username == "" and parts.password == ""
    assert join_proxy_url(parts) == "https://203.0.113.5:8443"



@pytest.mark.parametrize("host", [
    "a@1.2.3.4", "a/b", "a?b", "a#b", "a:b", "[::1]", "::1", "a b"])
def test_validate_proxy_host_rejects(host):
    with pytest.raises(ValueError, match="代理主机格式不正确"):
        validate_proxy_host(host)
    with pytest.raises(ValueError, match="代理主机格式不正确"):
        validate_proxy_host("")
    with pytest.raises(ValueError, match="代理主机格式不正确") as e:
        parse_provider_line(f"{host}|80|user|topsecret|2026-12-31")
    assert "topsecret" not in str(e.value)


@pytest.mark.parametrize("host", ["203.0.113.5", "proxy.example.com", "a-b.example"])
def test_validate_proxy_host_accepts(host):
    validate_proxy_host(host)
