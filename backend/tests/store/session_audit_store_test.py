import json

import sqlalchemy as sa

from app.domain.audit import CallRecord
from app.store import audit_store, session_store, shop_store
from app.store.session_store import SessionRow
from tests.store.conftest import LATER, NOW


def test_session_save_load_keeps_latest_only(engine):
    with engine.begin() as conn:
        sid = shop_store.create(conn, "A", NOW)
        assert session_store.load(conn, sid) is None
        session_store.save(conn, SessionRow(sid, b"c1", b"t1", "{}", "2027-01-01T00:00:00Z"), NOW)
        row2 = SessionRow(sid, b"c2", b"t2", '{"UA": "x"}', "2027-02-01T00:00:00Z")
        session_store.save(conn, row2, LATER)
        assert session_store.load(conn, sid) == row2
        assert conn.execute(sa.text("SELECT count(*) FROM session")).scalar() == 1


def test_audit_insert_redacts_summaries(engine):
    rec = CallRecord(None, "auth.login_ok", "admin", {"token": "t", "n": 1}, {"ok": True}, "ok", 12)
    with engine.begin() as conn:
        audit_store.insert(conn, rec, NOW)
        row = conn.execute(sa.text("SELECT * FROM audit_log")).one()
    assert row.actor == "admin" and row.shop_id is None and row.duration_ms == 12
    assert json.loads(row.req_summary) == {"token": "***", "n": 1}
    assert row.created_at == NOW
