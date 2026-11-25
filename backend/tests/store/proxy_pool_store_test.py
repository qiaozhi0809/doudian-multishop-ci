import pytest
import sqlalchemy as sa

from app.store import proxy_pool_store, shop_store
from tests.store.conftest import LATER, NOW


def _item(conn, identity="id-a", display="203.0.113.5:8000", expires_at=None, now=NOW):
    return proxy_pool_store.upsert(
        conn, identity=identity, proxy_url=b"CIPHER-" + identity.encode(),
        proxy_display=display, expires_at=expires_at, now=now,
    )


def _shop(conn, name, pool_id=None, status=None):
    sid = shop_store.create(conn, name, NOW)
    if status:
        shop_store.set_status(conn, sid, status, NOW)
    if pool_id is not None:
        shop_store.set_egress(conn, sid, NOW, egress_mode="proxy", proxy_pool_id=pool_id)
    return sid


def test_upsert_creates_and_get(engine):
    with engine.begin() as conn:
        pid = _item(conn, expires_at="2026-12-31")
        row = proxy_pool_store.get(conn, pid)
        assert row["identity"] == "id-a" and row["proxy_url"] == b"CIPHER-id-a"
        assert row["proxy_display"] == "203.0.113.5:8000" and row["expires_at"] == "2026-12-31"
        assert row["created_at"] == NOW and row["updated_at"] == NOW
        assert row["last_checked_at"] is None and row["last_check_ip"] is None
        assert proxy_pool_store.get_by_identity(conn, "id-a")["id"] == pid
        assert proxy_pool_store.get(conn, 999) is None
        assert proxy_pool_store.get_by_identity(conn, "nope") is None


def test_upsert_dedupes_and_keeps_expiry_when_none(engine):
    with engine.begin() as conn:
        pid = _item(conn, expires_at="2026-12-31")
        assert _item(conn, expires_at=None, now=LATER) == pid
        assert proxy_pool_store.get(conn, pid)["expires_at"] == "2026-12-31"
        assert _item(conn, expires_at="2027-01-31", now=LATER) == pid
        row = proxy_pool_store.get(conn, pid)
        assert row["expires_at"] == "2027-01-31" and row["updated_at"] == LATER
        assert len(proxy_pool_store.list_with_usage(conn)) == 1


def test_update_whitelist(engine):
    with engine.begin() as conn:
        pid = _item(conn)
        proxy_pool_store.update(conn, pid, LATER, last_checked_at=LATER, last_check_ip="1.2.3.4")
        row = proxy_pool_store.get(conn, pid)
        assert row["last_check_ip"] == "1.2.3.4" and row["updated_at"] == LATER
        with pytest.raises(ValueError):
            proxy_pool_store.update(conn, pid, LATER, created_at=LATER)


def test_unique_pool_index_ignores_disabled_shops(engine):
    with engine.begin() as conn:
        pid = _item(conn)
        _shop(conn, "停用店", pid, status="disabled")
        _shop(conn, "启用店", pid)
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        _shop(conn, "另一家启用店", pid)


def test_delete_referenced_item_violates_fk(engine):
    with engine.begin() as conn:
        pid = _item(conn)
        _shop(conn, "店A", pid, status="disabled")
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        proxy_pool_store.delete(conn, pid)
    with engine.begin() as conn:
        free = _item(conn, identity="id-b")
        proxy_pool_store.delete(conn, free)
        assert proxy_pool_store.get(conn, free) is None


def test_referrers_lists_all_shops(engine):
    with engine.begin() as conn:
        pid = _item(conn)
        _shop(conn, "停用店", pid, status="disabled")
        _shop(conn, "启用店", pid)
        refs = proxy_pool_store.referrers(conn, pid)
        assert [(r["name"], r["status"]) for r in refs] == [
            ("停用店", "disabled"), ("启用店", "needs_login")]


def test_list_with_usage_reports_only_enabled_shop(engine):
    with engine.begin() as conn:
        used = _item(conn, identity="id-a")
        idle = _item(conn, identity="id-b")
        _shop(conn, "停用店", idle, status="disabled")
        sid = _shop(conn, "启用店", used)
        rows = {r["id"]: r for r in proxy_pool_store.list_with_usage(conn)}
        assert rows[used]["in_use_shop_id"] == sid and rows[used]["in_use_shop_name"] == "启用店"
        assert rows[idle]["in_use_shop_id"] is None and rows[idle]["in_use_shop_name"] is None
        assert rows[used]["proxy_display"] == "203.0.113.5:8000"


def test_list_legacy(engine):
    with engine.begin() as conn:
        _item(conn, identity="legacy:1")
        _item(conn, identity="real")
        assert [r["identity"] for r in proxy_pool_store.list_legacy(conn)] == ["legacy:1"]


def test_shop_get_joins_pool_fields(engine):
    with engine.begin() as conn:
        pid = _item(conn, expires_at="2026-12-31")
        sid = _shop(conn, "店A", pid)
        bare = _shop(conn, "店B")
        row = shop_store.get(conn, sid)
        assert row["proxy_pool_id"] == pid and row["proxy_url"] == b"CIPHER-id-a"
        assert row["proxy_display"] == "203.0.113.5:8000"
        assert row["proxy_expires_at"] == "2026-12-31"
        assert shop_store.get(conn, bare)["proxy_url"] is None
        assert [r["proxy_display"] for r in shop_store.list(conn)] == ["203.0.113.5:8000", None]
