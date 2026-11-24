import dataclasses

import sqlalchemy as sa

from app.domain.order_status import LocalOrderStatus
from app.store import order_store, shop_store
from tests.store.builders import make_item, make_order
from tests.store.conftest import LATER, NOW


def _shop(conn, name="店A"):
    return shop_store.create(conn, name, NOW)


def _status(conn, shop_id, order_no):
    return conn.execute(
        sa.text("SELECT status, platform_status FROM orders WHERE shop_id=:s AND order_no=:o"),
        {"s": shop_id, "o": order_no},
    ).one()


def test_upsert_new_order_is_synced(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        assert order_store.upsert_orders(conn, sid, [make_order("o1")], NOW) == 1
        assert _status(conn, sid, "o1").status == "synced"


def test_upsert_keeps_local_status(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        order_store.upsert_orders(conn, sid, [make_order("o1")], NOW)
        order_store.set_local_status(conn, sid, "o1", LocalOrderStatus.PENDING_LABEL, NOW)
        order_store.upsert_orders(conn, sid, [make_order("o1", platform_status=4)], LATER)
        row = _status(conn, sid, "o1")
        assert row.status == "pending_label"
        assert row.platform_status == 4


def test_upsert_replaces_items(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        two = (make_item("a"), make_item("b"))
        order_store.upsert_orders(conn, sid, [make_order("o1", items=two)], NOW)
        order_store.upsert_orders(conn, sid, [make_order("o1", items=(make_item("c"),))], LATER)
        ids = [r[0] for r in conn.execute(sa.text("SELECT sku_order_id FROM order_items"))]
        assert ids == ["c"]


def test_same_order_no_in_two_shops(engine):
    with engine.begin() as conn:
        a, b = _shop(conn, "A"), _shop(conn, "B")
        order_store.upsert_orders(conn, a, [make_order("o1")], NOW)
        order_store.upsert_orders(conn, b, [make_order("o1")], NOW)
        rows, total = order_store.list_orders(conn, [a], None, 1, 10)
        assert total == 1 and rows[0]["shop_id"] == a


def test_list_orders_paging(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        orders = [make_order(f"o{i:02d}", pay_time=f"2026-11-24T10:{i:02d}:00Z") for i in range(25)]
        order_store.upsert_orders(conn, sid, orders, NOW)
        rows, total = order_store.list_orders(conn, [sid], None, 2, 10)
        assert len(rows) == 10 and total == 25
        assert rows[0]["order_no"] == "o14"  # pay_time 倒序，第 2 页从第 11 新的开始
        rows, _ = order_store.list_orders(conn, [sid], None, 3, 10)
        assert len(rows) == 5


def test_list_orders_filters(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        order_store.upsert_orders(conn, sid, [make_order("o1"), make_order("o2")], NOW)
        order_store.set_local_status(conn, sid, "o2", LocalOrderStatus.PRINTED, NOW)
        rows, total = order_store.list_orders(conn, [sid], LocalOrderStatus.PRINTED, 1, 10)
        assert [r["order_no"] for r in rows] == ["o2"] and total == 1
        assert order_store.list_orders(conn, [], None, 1, 10) == ([], 0)


def test_recheck_excludes_platform_final(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        order_store.upsert_orders(
            conn, sid,
            [make_order("a", platform_status=2), make_order("b", platform_status=3),
             make_order("c", platform_status=4), make_order("d", platform_status=5),
             make_order("e", platform_status=None)],
            NOW,
        )
        assert order_store.recheck_candidates(conn, sid) == {"a", "e"}


def test_recheck_excludes_local_final(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        batch = [make_order("a"), make_order("b"), make_order("c")]
        order_store.upsert_orders(conn, sid, batch, NOW)
        order_store.set_local_status(conn, sid, "a", LocalOrderStatus.SHIPPED, NOW)
        order_store.set_local_status(conn, sid, "b", LocalOrderStatus.CANCELLED, NOW)
        assert order_store.recheck_candidates(conn, sid) == {"c"}


def test_upsert_stores_raw_json_and_fields(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        order = dataclasses.replace(make_order("o1"), raw={"中": 1})
        order_store.upsert_orders(conn, sid, [order], NOW)
        row = conn.execute(sa.text("SELECT raw_json, amount_cents, synced_at FROM orders")).one()
        assert row.raw_json == '{"中": 1}' and row.amount_cents == 1000 and row.synced_at == NOW
