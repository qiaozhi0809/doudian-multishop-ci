from datetime import UTC, datetime, timedelta

from app.domain.auth_rules import after_failure, session_alive, validate_password

NOW = datetime(2026, 12, 1, 0, 0, 0, tzinfo=UTC)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def test_password_rules():
    assert validate_password("12345678") == []
    assert validate_password("1234567")  # 少于 8 位
    assert validate_password("")
    assert validate_password("密码密码密码密码") == []  # 按字符数计


def test_lock_and_relock():
    count, locked = 0, None
    for expected in (1, 2, 3, 4):
        count, locked = after_failure(count, NOW)
        assert (count, locked) == (expected, None)
    count, locked = after_failure(count, NOW)  # 第 5 次：锁定 5 分钟并清零计数
    assert count == 0 and locked == _iso(NOW + timedelta(minutes=5))
    later = NOW + timedelta(minutes=6)  # 锁定到期后再错 5 次，再次锁定
    for _ in range(4):
        count, locked = after_failure(count, later)
        assert locked is None
    count, locked = after_failure(count, later)
    assert locked == _iso(later + timedelta(minutes=5))


def test_session_idle_and_absolute():
    created = _iso(NOW)
    assert session_alive(created, created, NOW + timedelta(hours=12)) is True
    assert session_alive(created, created, NOW + timedelta(hours=12, seconds=1)) is False
    last_seen = _iso(NOW + timedelta(days=6, hours=20))  # 一直在用，但自创建超过 7 天
    assert session_alive(created, last_seen, NOW + timedelta(days=7, seconds=1)) is False
    assert session_alive(created, last_seen, NOW + timedelta(days=6, hours=21)) is True
