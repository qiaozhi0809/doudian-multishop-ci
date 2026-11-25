"""print_job 表与存储（data-model 6.2 ⑤-b）：每次打印尝试一条，可追溯。"""

import sqlalchemy as sa

from app.domain.print_status import PrintJobStatus
from app.store import print_job_store, shop_store, waybill_store
from app.store.schema import orders

NOW = "2026-11-25T00:00:00Z"
LATER = "2026-11-25T00:05:00Z"


def seed_waybill(engine, order_no="6900000000000000001", waybill_no="79200000000001") -> int:
    with engine.begin() as conn:
        shop_id = shop_store.create(conn, "店A", NOW)
        order_id = conn.execute(sa.insert(orders).values(
            shop_id=shop_id, order_no=order_no, status="label_obtained",
            platform_status=2, synced_at=NOW,
        )).inserted_primary_key[0]
        return waybill_store.insert(
            conn, shop_id=shop_id, order_id=int(order_id), seq=1, courier_code="zhongtong",
            waybill_no=waybill_no, print_data="pd", sign="sg", template_code="t1",
            exp_type="defaultProductType", ebill_id="e1", net_code="n1",
            status="active", now=NOW,
        )


def test_insert_creates_queued_job(engine):
    wid = seed_waybill(engine)
    with engine.begin() as conn:
        job_id = print_job_store.insert(conn, waybill_id=wid, printer_name="A", now=NOW)
    with engine.connect() as conn:
        job = print_job_store.get(conn, job_id)
    assert job["waybill_id"] == wid
    assert job["printer_name"] == "A"
    assert job["status"] == PrintJobStatus.QUEUED.value
    assert job["attempts"] == 0
    assert job["result_code"] is None and job["finished_at"] is None


def test_bump_attempts_counts_component_attempts(engine):
    wid = seed_waybill(engine)
    with engine.begin() as conn:
        job_id = print_job_store.insert(conn, waybill_id=wid, printer_name="A", now=NOW)
        print_job_store.bump_attempts(conn, job_id, 1)
        print_job_store.bump_attempts(conn, job_id, 2)
    with engine.connect() as conn:
        assert print_job_store.get(conn, job_id)["attempts"] == 2


def test_finish_records_result(engine):
    wid = seed_waybill(engine)
    with engine.begin() as conn:
        job_id = print_job_store.insert(conn, waybill_id=wid, printer_name="A", now=NOW)
        print_job_store.finish(
            conn, job_id, PrintJobStatus.FAILED, "component_failed", "缺纸", LATER)
    with engine.connect() as conn:
        job = print_job_store.get(conn, job_id)
    assert job["status"] == "failed"
    assert job["result_code"] == "component_failed"
    assert job["result_detail"] == "缺纸"
    assert job["finished_at"] == LATER


def test_latest_by_waybills_picks_newest(engine):
    wid1 = seed_waybill(engine, order_no="o1", waybill_no="w1")
    wid2 = seed_waybill(engine, order_no="o2", waybill_no="w2")
    with engine.begin() as conn:
        first = print_job_store.insert(conn, waybill_id=wid1, printer_name="A", now=NOW)
        print_job_store.finish(conn, first, PrintJobStatus.FAILED, "x", None, LATER)
        latest = print_job_store.insert(conn, waybill_id=wid1, printer_name="A", now=LATER)
        print_job_store.insert(conn, waybill_id=wid2, printer_name="A", now=NOW)
    with engine.connect() as conn:
        rows = print_job_store.latest_by_waybills(conn, [wid1, wid2])
        missing = print_job_store.latest_by_waybills(conn, [999])
    assert rows[wid1]["id"] == latest
    assert rows[wid1]["status"] == "queued"
    assert wid2 in rows
    assert missing == {}


def test_by_ids_and_waybill_ids(engine):
    wid = seed_waybill(engine)
    with engine.begin() as conn:
        job1 = print_job_store.insert(conn, waybill_id=wid, printer_name="A", now=NOW)
        job2 = print_job_store.insert(conn, waybill_id=wid, printer_name="B", now=LATER)
        assert [r["id"] for r in print_job_store.by_ids(conn, [job2, job1])] == [job1, job2]
        all_ids = print_job_store.ids_by_waybills(conn, [wid])
    assert set(all_ids) == {job1, job2}


def test_printer_name_is_required(engine):
    wid = seed_waybill(engine)
    try:
        with engine.begin() as conn:
            print_job_store.insert(conn, waybill_id=wid, printer_name=None, now=NOW)
    except sa.exc.IntegrityError:
        pass
    else:
        raise AssertionError("printer_name 不应允许 NULL")
