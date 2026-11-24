from datetime import UTC, datetime, timedelta

from app.domain.session_health import health_from_expiry

NOW = datetime(2026, 11, 25, 0, 0, 0, tzinfo=UTC)


def _iso(delta: timedelta) -> str:
    return (NOW + delta).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_health_thresholds():
    assert health_from_expiry(_iso(timedelta(days=8)), NOW) == "healthy"
    assert health_from_expiry(_iso(timedelta(days=7)), NOW) == "expiring"
    assert health_from_expiry(_iso(timedelta(days=1)), NOW) == "expiring"
    assert health_from_expiry(_iso(timedelta(seconds=1)), NOW) == "expiring"
    assert health_from_expiry(_iso(timedelta(0)), NOW) == "expired"
    assert health_from_expiry(_iso(timedelta(days=-3)), NOW) == "expired"


def test_unknown_expiry_is_expired():
    assert health_from_expiry(None, NOW) == "expired"
