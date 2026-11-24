import pytest

from app.shared.time_bj import parse_platform_time, to_biz_date


def test_parse_unix_seconds():
    assert parse_platform_time(1764000000) == "2025-11-24T16:00:00Z"
    assert parse_platform_time("1764000000") == "2025-11-24T16:00:00Z"


def test_parse_beijing_string():
    assert parse_platform_time("2026-11-25 08:00:00") == "2026-11-25T00:00:00Z"


def test_parse_empty():
    assert parse_platform_time(None) is None
    assert parse_platform_time(0) is None
    assert parse_platform_time("") is None


def test_parse_garbage_raises():
    with pytest.raises(ValueError):
        parse_platform_time("not-a-time")


def test_biz_date_crosses_midnight():
    assert to_biz_date("2026-11-24T16:30:00Z") == "2026-11-25"
    assert to_biz_date("2026-11-24T15:59:59Z") == "2026-11-24"
