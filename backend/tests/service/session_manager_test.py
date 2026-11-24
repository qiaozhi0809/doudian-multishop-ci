import pytest
import sqlalchemy as sa

from app.adapter.browser.login import LoginResult
from app.adapter.doudian.errors import SessionExpired
from app.service.events import EventBus
from app.service.session_manager import SessionManager
from app.shared.secret_box import DevKeyBox
from app.store import shop_store

TOKEN = "tok_" + "x" * 8
COOKIE_VAL = "ck_" + "y" * 8
NOW = "2026-11-25T00:00:00Z"


def _login_result() -> LoginResult:
    return LoginResult(
        cookies=[{"name": "sessionid", "value": COOKIE_VAL, "domain": ".jinritemai.com",
                  "path": "/"}],
        token=TOKEN,
        expires_at="2027-01-24T00:00:00Z",
        device_headers={"User-Agent": "UA/1"},
    )


@pytest.fixture
def env(engine, tmp_path):
    events = EventBus()
    mgr = SessionManager(engine, DevKeyBox(tmp_path / "k"), events)
    with engine.begin() as conn:
        shop_id = shop_store.create(conn, "店A", NOW)
    return mgr, events, shop_id, engine


def _shop(engine, shop_id):
    with engine.connect() as conn:
        return shop_store.get(conn, shop_id)


async def test_save_login_encrypts(env):
    mgr, events, shop_id, engine = env
    sub = events.subscribe()
    mgr.save_login(shop_id, _login_result())
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT cookies, token, device_params FROM session")).one()
    assert TOKEN.encode() not in row.token and COOKIE_VAL.encode() not in row.cookies
    assert _shop(engine, shop_id)["status"] == "active"
    assert await anext(sub) == (
        "shop_status_changed", {"shop_id": shop_id, "status": "active", "health": "healthy"}
    )


def test_get_credentials_roundtrip(env):
    mgr, _, shop_id, _ = env
    mgr.save_login(shop_id, _login_result())
    creds = mgr.get_credentials(shop_id)
    assert creds.shop_id == shop_id and creds.token == TOKEN
    assert creds.cookies[0]["value"] == COOKIE_VAL
    assert creds.device_headers == {"User-Agent": "UA/1"}


def test_save_login_replaces_previous(env):
    mgr, _, shop_id, _ = env
    mgr.save_login(shop_id, _login_result())
    newer = LoginResult([], "tok_" + "z" * 8, "2027-02-01T00:00:00Z", {})
    mgr.save_login(shop_id, newer)
    assert mgr.get_credentials(shop_id).token == "tok_" + "z" * 8


async def test_mark_expired_publishes(env):
    mgr, events, shop_id, engine = env
    mgr.save_login(shop_id, _login_result())
    sub = events.subscribe()
    mgr.mark_expired(shop_id)
    assert _shop(engine, shop_id)["status"] == "needs_login"
    assert await anext(sub) == (
        "shop_status_changed", {"shop_id": shop_id, "status": "needs_login", "health": "expired"}
    )


def test_get_credentials_needs_login_raises(env):
    mgr, _, shop_id, _ = env
    with pytest.raises(SessionExpired):  # 新店：无会话
        mgr.get_credentials(shop_id)
    mgr.save_login(shop_id, _login_result())
    mgr.mark_expired(shop_id)
    with pytest.raises(SessionExpired):  # 有会话但已标记失效
        mgr.get_credentials(shop_id)


def test_unknown_shop(env):
    mgr, *_ = env
    with pytest.raises(LookupError):
        mgr.save_login(999, _login_result())
    with pytest.raises(SessionExpired):
        mgr.get_credentials(999)
