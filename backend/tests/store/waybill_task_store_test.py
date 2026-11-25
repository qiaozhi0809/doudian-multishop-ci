"""waybills / tasks 表与存储（data-model 6.2 ⑤⑥、backend 5.11）。"""

import sqlalchemy as sa

from app.domain.task_status import TaskStatus, TaskType
from app.store import shop_store, task_store, waybill_store
from app.store.schema import orders

NOW = "2026-11-25T00:00:00Z"
LATER = "2026-11-25T00:05:00Z"


def seed_order(engine, order_no="6900000000000000001", status="pending_label") -> tuple[int, int]:
    with engine.begin() as conn:
        shop_id = shop_store.create(conn, "店A", NOW)
        order_id = conn.execute(sa.insert(orders).values(
            shop_id=shop_id, order_no=order_no, status=status, platform_status=2,
            synced_at=NOW,
        )).inserted_primary_key[0]
    return shop_id, int(order_id)


def add_waybill(engine, shop_id, order_id, *, seq=1, waybill_no="79200000000001",
                status="active", courier="zhongtong"):
    with engine.begin() as conn:
        return waybill_store.insert(
            conn, shop_id=shop_id, order_id=order_id, seq=seq, courier_code=courier,
            waybill_no=waybill_no, print_data="pd", sign="sg", template_code="t1",
            exp_type="defaultProductType", ebill_id="e1", net_code="n1", status=status, now=NOW,
        )


# ---- waybills ----

def test_insert_and_active_lookup(engine):
    shop_id, order_id = seed_order(engine)
    wid = add_waybill(engine, shop_id, order_id)
    with engine.connect() as conn:
        active = waybill_store.active_by_orders(conn, [order_id])
    assert active[order_id]["id"] == wid
    assert active[order_id]["waybill_no"] == "79200000000001"


def test_printed_waybill_also_occupies_active_slot(engine):
    shop_id, order_id = seed_order(engine)
    add_waybill(engine, shop_id, order_id, status="printed")
    with engine.connect() as conn:
        assert order_id in waybill_store.active_by_orders(conn, [order_id])
    try:
        add_waybill(engine, shop_id, order_id, seq=2, waybill_no="79200000000002")
    except sa.exc.IntegrityError:
        pass
    else:
        raise AssertionError("同一订单不应同时存在两张有效面单")


def test_void_then_reobtain_allowed(engine):
    shop_id, order_id = seed_order(engine)
    wid = add_waybill(engine, shop_id, order_id)
    with engine.begin() as conn:
        waybill_store.mark_void(conn, wid, LATER)
        assert waybill_store.voided_count(conn, order_id) == 1
    wid2 = add_waybill(engine, shop_id, order_id, seq=2, waybill_no="79200000000002")
    assert wid2 != wid


def test_waybill_no_globally_unique(engine):
    shop_id, order1 = seed_order(engine, "o1")
    _, order2 = seed_order(engine, "o2")
    add_waybill(engine, shop_id, order1, waybill_no="79200000000009")
    try:
        add_waybill(engine, shop_id, order2, waybill_no="79200000000009")
    except sa.exc.IntegrityError:
        pass
    else:
        raise AssertionError("同一运单号不应入库两次")


def test_list_by_orders(engine):
    shop_id, order1 = seed_order(engine, "o1")
    _, order2 = seed_order(engine, "o2")
    add_waybill(engine, shop_id, order1, waybill_no="L1")
    with engine.connect() as conn:
        rows = waybill_store.list_by_orders(conn, [order1, order2])
    assert len(rows[order1]) == 1 and rows[order2] == []


# ---- tasks ----

def test_task_start_creates_once_and_reuses_running(engine):
    shop_id, order_id = seed_order(engine)
    key = "label:1:o1:1"
    with engine.begin() as conn:
        first = task_store.start(
            conn, key=key, shop_id=shop_id, type=TaskType.OBTAIN_LABEL.value,
            payload={"order_id": order_id}, actor="admin", now=NOW)
        second = task_store.start(
            conn, key=key, shop_id=shop_id, type=TaskType.OBTAIN_LABEL.value,
            payload={}, actor="admin", now=LATER)
        total = conn.execute(sa.select(sa.func.count()).select_from(task_store.tasks)).scalar_one()
    assert first["id"] == second["id"]
    assert second["attempts"] == 1  # 运行中不重复计数
    assert total == 1


def test_task_failed_retry_increments_attempts(engine):
    shop_id, _ = seed_order(engine)
    key = "label:1:o1:1"
    with engine.begin() as conn:
        task = task_store.start(
            conn, key=key, shop_id=shop_id, type=TaskType.OBTAIN_LABEL.value,
            payload={}, actor="admin", now=NOW)
        task_store.finish(conn, task["id"], TaskStatus.FAILED, "boom", NOW)
        retried = task_store.start(
            conn, key=key, shop_id=shop_id, type=TaskType.OBTAIN_LABEL.value,
            payload={}, actor="admin", now=LATER)
    assert retried["id"] == task["id"]
    assert retried["attempts"] == 2
    assert retried["status"] == TaskStatus.RUNNING.value
    assert retried["last_error"] is None


def test_task_success_is_not_rerun(engine):
    shop_id, _ = seed_order(engine)
    key = "label:1:o1:1"
    with engine.begin() as conn:
        task = task_store.start(
            conn, key=key, shop_id=shop_id, type=TaskType.OBTAIN_LABEL.value,
            payload={}, actor="admin", now=NOW)
        task_store.finish(conn, task["id"], TaskStatus.SUCCESS, None, NOW)
        again = task_store.start(
            conn, key=key, shop_id=shop_id, type=TaskType.OBTAIN_LABEL.value,
            payload={}, actor="admin", now=LATER)
    assert again["status"] == TaskStatus.SUCCESS.value
    assert again["attempts"] == 1
