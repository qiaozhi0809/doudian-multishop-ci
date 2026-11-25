"""ShopAdminService.create：添加店铺时一并绑定出口（同一事务）。"""

from datetime import UTC, datetime

import pytest
import sqlalchemy as sa

from app.domain.egress_rules import proxy_identity
from app.service.egress import EgressService, ProxyPoolInUse
from app.service.events import SHOP_STATUS_CHANGED, EventBus
from app.service.shop_admin import ShopAdminService
from app.shared.secret_box import DevKeyBox
from app.store import proxy_pool_store, shop_store

NOW = datetime(2026, 12, 1, tzinfo=UTC)
PW = "pw-not-in-ciphertext"
URL = f"http://user-x-not-in-ciphertext:{PW}@203.0.113.5:8000"


@pytest.fixture
def env(engine, tmp_path):
    events = EventBus()
    seen: list[tuple[str, dict]] = []
    events.publish = lambda topic, data: seen.append((topic, data))  # type: ignore[method-assign]
    box = DevKeyBox(tmp_path / "k")
    egress = EgressService(engine, box, events, None, clock=lambda: NOW)  # type: ignore[arg-type]
    admin = ShopAdminService(engine, events, egress, clock=lambda: NOW)
    return type("Env", (), {"engine": engine, "admin": admin, "box": box, "seen": seen})


def _names(env) -> list[str]:
    with env.engine.connect() as conn:
        return [s["name"] for s in shop_store.list(conn)]


def _pool_item(env) -> int:
    with env.engine.begin() as conn:
        return proxy_pool_store.upsert(
            conn, identity=proxy_identity(URL), proxy_url=env.box.encrypt(URL.encode()),
            proxy_display="203.0.113.5:8000", expires_at=None, now="2026-11-25T00:00:00Z")


def _get(env, sid):
    with env.engine.connect() as conn:
        return shop_store.get(conn, sid)


def test_create_with_pool_item_binds_in_same_transaction(env):
    pid = _pool_item(env)
    sid = env.admin.create("店B", egress={"mode": "proxy", "pool_id": pid})
    row = _get(env, sid)
    assert row["proxy_pool_id"] == pid and row["egress_mode"] == "proxy"
    assert env.seen[-1][0] == SHOP_STATUS_CHANGED
    assert env.seen[-1][1]["shop_id"] == sid and env.seen[-1][1]["egress_status"] == "unchecked"


def test_create_with_taken_item_creates_nothing(env):
    pid = _pool_item(env)
    env.admin.create("店A", egress={"mode": "proxy", "pool_id": pid})
    with pytest.raises(ProxyPoolInUse):
        env.admin.create("店C", egress={"mode": "proxy", "pool_id": pid})
    assert _names(env) == ["店A"]


def test_create_with_race_integrity_error_creates_nothing(env, monkeypatch):
    pid = _pool_item(env)
    env.admin.create("店A", egress={"mode": "proxy", "pool_id": pid})
    monkeypatch.setattr(EgressService, "_ensure_pool_free", staticmethod(lambda *a: None))
    with pytest.raises(ProxyPoolInUse):
        env.admin.create("店C", egress={"mode": "proxy", "pool_id": pid})
    assert _names(env) == ["店A"]


def test_create_with_bad_paste_creates_nothing(env):
    with pytest.raises(ValueError):
        env.admin.create("店D", egress={"mode": "proxy", "paste": "not|valid"})
    assert _names(env) == []


def test_create_without_egress_unchanged(env):
    sid = env.admin.create("店E")
    row = _get(env, sid)
    assert row["proxy_pool_id"] is None and row["status"] == "needs_login"
    assert env.seen == []


def test_create_with_paste_leaks_no_password_in_audit(env):
    sid = env.admin.create(
        "店F", egress={"mode": "proxy", "paste": f"203.0.113.9|8000|acct-x|{PW}|2027-01-01"})
    assert _get(env, sid)["proxy_pool_id"] is not None
    with env.engine.connect() as conn:
        dump = " ".join(str(tuple(r)) for r in conn.execute(sa.text("select * from audit_log")))
    assert dump and PW not in dump
