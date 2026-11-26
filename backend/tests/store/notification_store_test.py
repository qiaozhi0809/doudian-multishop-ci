import pytest
import sqlalchemy as sa

from app.store import notification_store as ns
from app.store import shop_store, sync_baseline_store
from tests.store.conftest import LATER, NOW

T1, T2, T3 = "2026-11-25T01:00:00Z", "2026-11-25T02:00:00Z", "2026-11-25T03:00:00Z"


def _ins(conn, *, at=NOW, **kw):
    f = {"kind": "k", "level": "info", "title": "t", "created_at": at, "updated_at": at}
    f.update(kw)
    return ns.insert(conn, **f)


def test_insert_get_roundtrip(engine):
    with engine.begin() as conn:
        sid = shop_store.create(conn, "测试店", NOW)
        nid = _ins(conn, shop_id=sid, body="b", link="/x")
        row = ns.get(conn, nid)
        assert row["kind"] == "k" and row["shop_id"] == sid and row["body"] == "b"
        assert row["count"] == 1 and row["read_at"] is None and row["state_key"] is None
        assert ns.get(conn, 999) is None


def test_update_whitelist(engine):
    with engine.begin() as conn:
        nid = _ins(conn)
        ns.update(conn, nid, LATER, title="新", count=3)
        row = ns.get(conn, nid)
        assert row["title"] == "新" and row["count"] == 3 and row["updated_at"] == LATER
        with pytest.raises(ValueError):
            ns.update(conn, nid, LATER, state_key="x")


def test_open_state_unique(engine):
    with engine.begin() as conn:
        _ins(conn, state_key="s1")
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        _ins(conn, state_key="s1")


def test_resolved_and_open_coexist(engine):
    with engine.begin() as conn:
        a = _ins(conn, state_key="s1", resolved_at=T1)
        b = _ins(conn, state_key="s1")
        assert ns.open_state(conn, "s1")["id"] == b
        assert ns.open_state(conn, "none") is None
        ns.update(conn, b, T2, resolved_at=T2)
        assert ns.open_state(conn, "s1") is None
        assert ns.last_resolved_state(conn, "s1")["id"] == b
        assert a != b


def test_latest_unread_event(engine):
    with engine.begin() as conn:
        s1 = shop_store.create(conn, "甲", NOW)
        s2 = shop_store.create(conn, "乙", NOW)
        _ins(conn, shop_id=s1, at=T1)
        new = _ins(conn, shop_id=s1, at=T2)
        _ins(conn, shop_id=s2, at=T3)
        _ins(conn, shop_id=s1, at=T3, state_key="st")
        assert ns.latest_unread_event(conn, s1, "k")["id"] == new
        ns.mark_read(conn, new, T3)
        assert ns.latest_unread_event(conn, s1, "k")["created_at"] == T1
        assert ns.latest_unread_event(conn, s1, "other") is None


def test_list_page_unread_only_ordered(engine):
    with engine.begin() as conn:
        a = _ins(conn, at=T1)
        b = _ins(conn, at=T3)
        c = _ins(conn, at=T2)
        d = _ins(conn, at=T3)
        ns.mark_read(conn, d, T3)
        rows, total = ns.list_page(conn, unread_only=True, offset=0, limit=10)
        assert [r["id"] for r in rows] == [b, c, a] and total == 3
        rows, total = ns.list_page(conn, unread_only=False, offset=0, limit=2)
        assert len(rows) == 2 and total == 4
        rows, _ = ns.list_page(conn, unread_only=True, offset=1, limit=1)
        assert [r["id"] for r in rows] == [c]


def test_unread_count_and_mark_read(engine):
    with engine.begin() as conn:
        a = _ins(conn)
        _ins(conn)
        assert ns.unread_count(conn) == 2
        ns.mark_read(conn, a, T1)
        ns.mark_read(conn, a, T2)
        assert ns.get(conn, a)["read_at"] == T1 and ns.unread_count(conn) == 1
        ns.mark_all_read(conn, T3)
        assert ns.unread_count(conn) == 0 and ns.get(conn, a)["read_at"] == T1


def test_unread_count_skips_open_states(engine):
    with engine.begin() as conn:
        _ins(conn)
        _ins(conn, level="strong", state_key="open")
        _ins(conn, level="strong", state_key="done", resolved_at=T1)
        assert ns.unread_count(conn) == 2
        # 未解决但不是强档：横条不代表它，照常计入未读
        _ins(conn, level="medium", state_key="medium")
        assert ns.unread_count(conn) == 3


def test_open_strong_states(engine):
    with engine.begin() as conn:
        _ins(conn, level="strong")
        _ins(conn, level="strong", state_key="x", resolved_at=T1)
        _ins(conn, level="medium", state_key="z")
        open_id = _ins(conn, level="strong", state_key="y")
        assert [r["id"] for r in ns.open_strong_states(conn)] == [open_id]


def test_purge_read_events_before(engine):
    with engine.begin() as conn:
        old_read = _ins(conn, at=T1, read_at=T1)
        old_unread = _ins(conn, at=T1)
        old_open = _ins(conn, at=T1, read_at=T1, state_key="open")
        old_resolved = _ins(conn, at=T1, read_at=T1, state_key="done", resolved_at=T1)
        new_read = _ins(conn, at=T3, read_at=T3)
        assert ns.purge_read_events_before(conn, T2) == 2
        assert ns.get(conn, old_read) is None and ns.get(conn, old_resolved) is None
        for keep in (old_unread, old_open, new_read):
            assert ns.get(conn, keep) is not None


def test_sync_baseline_establish_idempotent(engine):
    with engine.begin() as conn:
        sid = shop_store.create(conn, "测试店", NOW)
        assert not sync_baseline_store.has(conn, sid, "order")
        sync_baseline_store.establish(conn, sid, "order", NOW)
        sync_baseline_store.establish(conn, sid, "order", LATER)
        assert sync_baseline_store.has(conn, sid, "order")
        assert not sync_baseline_store.has(conn, sid, "aftersale")
        got = conn.execute(sa.text("SELECT established_at FROM sync_baseline")).scalar_one()
        assert got == NOW



def test_latest_unread_event_filters_by_link(engine):
    with engine.begin() as conn:
        sid = shop_store.create(conn, "测试店", NOW)
        a = _ins(conn, shop_id=sid, kind="sync_failed", link="/orders", at=T1)
        _ins(conn, shop_id=sid, kind="sync_failed", link="/aftersale", at=T2)
        assert ns.latest_unread_event(conn, sid, "sync_failed", link="/orders")["id"] == a
        assert ns.latest_unread_event(conn, sid, "sync_failed", link="/stock") is None


def test_update_kind_and_recovered_marker(engine):
    with engine.begin() as conn:
        nid = _ins(conn, state_key="s")
        ns.update(conn, nid, LATER, kind="k2", recovered_notified_at=LATER)
        row = ns.get(conn, nid)
        assert row["kind"] == "k2" and row["recovered_notified_at"] == LATER
