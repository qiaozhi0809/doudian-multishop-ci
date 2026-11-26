import pytest
import sqlalchemy as sa

from app.store import shop_store
from tests.store.conftest import LATER, NOW


def _shop(conn, name="店A"):
    return shop_store.create(conn, name, NOW)


def test_create_get_list(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        _shop(conn, "店B")
        row = shop_store.get(conn, sid)
        assert row["name"] == "店A" and row["status"] == "needs_login"
        assert row["egress_status"] == "unchecked" and row["paused_reason"] is None
        assert [r["name"] for r in shop_store.list(conn)] == ["店A", "店B"]
        assert shop_store.get(conn, 999) is None


def test_set_status_and_paused(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        shop_store.set_status(conn, sid, "active", LATER)
        shop_store.set_paused(conn, sid, "risk_blocked:602502151", LATER)
        row = shop_store.get(conn, sid)
        assert row["status"] == "active" and row["updated_at"] == LATER
        assert row["paused_reason"] == "risk_blocked:602502151" and row["paused_at"] == LATER
        shop_store.set_paused(conn, sid, None, LATER)
        row = shop_store.get(conn, sid)
        assert row["paused_reason"] is None and row["paused_at"] is None


def test_update_fields_im_enabled(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        assert shop_store.get(conn, sid)["im_enabled"] == 0
        shop_store.update_fields(conn, sid, LATER, im_enabled=1)
        row = shop_store.get(conn, sid)
        assert row["im_enabled"] == 1 and row["updated_at"] == LATER
        shop_store.update_fields(conn, sid, LATER, im_enabled=0)
        assert shop_store.get(conn, sid)["im_enabled"] == 0


def test_set_egress_rejects_unknown_column(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        with pytest.raises(ValueError):
            shop_store.set_egress(conn, sid, NOW, status="x")


def test_second_direct_violates_index(engine):
    with engine.begin() as conn:
        a, b = _shop(conn, "A"), _shop(conn, "B")
        shop_store.set_egress(conn, a, NOW, egress_mode="direct")
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        shop_store.set_egress(conn, b, NOW, egress_mode="direct")


def test_disabled_shop_does_not_hold_direct_or_ip(engine):
    with engine.begin() as conn:
        a, b = _shop(conn, "A"), _shop(conn, "B")
        shop_store.set_egress(conn, a, NOW, egress_mode="direct", egress_ip="1.1.1.1")
        shop_store.set_status(conn, a, "disabled", NOW)
        shop_store.set_egress(conn, b, NOW, egress_mode="direct", egress_ip="1.1.1.1")


def test_duplicate_egress_ip_violates_index(engine):
    with engine.begin() as conn:
        a, b = _shop(conn, "A"), _shop(conn, "B")
        shop_store.set_egress(conn, a, NOW, egress_ip="1.1.1.1")
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        shop_store.set_egress(conn, b, NOW, egress_ip="1.1.1.1")
