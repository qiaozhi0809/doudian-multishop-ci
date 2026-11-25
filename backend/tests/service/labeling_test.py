"""执行（第③步）：取号 / 一体 / 作废 / 超时查回（backend 5.5 / 5.11 / 5.12）。"""

import json
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.adapter.doudian.errors import TransientError
from app.adapter.doudian.transport import TransportResponse
from app.domain.errors import DryRunBlocked
from app.service.events import LABEL_DONE, LABEL_PROGRESS
from app.service.labeling import RunSummary
from app.store import shop_store
from app.store.schema import orders
from tests.fakes import ok, reply
from tests.service.label_support import LabelExecEnv

WRITE = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "write"
ORDER1 = "6900000000000000001"
ORDER2 = "6900000000000000002"
ORDER3 = "6900000000000000003"
PT = {"logistics_product": [{"param": "expType", "selectedValue": "defaultProductType"}],
      "added_services": []}


def fx(name: str) -> TransportResponse:
    return TransportResponse(200, (WRITE / f"{name}.json").read_bytes())


def pt_ok() -> TransportResponse:
    return ok(PT)


async def execute(env: LabelExecEnv, order_ids, *, mode="obtain", courier=None):
    record = env.previews.preview_obtain(order_ids, courier or {}, actor="admin", mode=mode)
    return await env.service.execute_inline(record.preview_id, "admin")


def collect_events(env) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    original = env.events.publish

    def recording(event, data):
        events.append((event, data))
        original(event, data)

    env.events.publish = recording
    return events


# ---- 打面单 ----

async def test_obtain_success(engine, tmp_path, clock):
    env = LabelExecEnv(engine, tmp_path, clock, [pt_ok(), fx("batch_fetch_tracking_nos")])
    oid = env.add_order(ORDER1)
    events = collect_events(env)

    summary = await execute(env, [oid])

    assert summary == RunSummary(ok=1, failed=0, verifying=0, skipped=0)
    waybill = env.waybills(oid)[0]
    assert waybill["waybill_no"] == "79200000000001"
    assert waybill["status"] == "active"
    assert waybill["seq"] == 1
    # M3 打印需要：print_data / sign / 模板 / 账户 / 网点 / 产品类型
    assert waybill["print_data"] == "PRINT_DATA_PLACEHOLDER"
    assert waybill["sign"] == "SIGN_PLACEHOLDER"
    assert waybill["logistics_template_code"] == "C1m77ow4c2qrrd"
    assert waybill["ebill_id"] == "e1"
    assert waybill["net_code"] == "n1"
    assert waybill["exp_type"] == "defaultProductType"
    assert env.order(oid)["status"] == "label_obtained"
    assert env.task_by_key(f"label:1:{ORDER1}:1")["status"] == "success"

    urls = [r["url"] for r in env.transport.requests]
    assert "query_added_services_and_product_types" in urls[0]
    assert urls[1].endswith("/api/order/batchFetchTrackingNos")
    body = env.transport.requests[1]["json"]
    assert body["transport"] == '{"expType": "defaultProductType"}'
    assert body["logistics_company_code"] == "zhongtong"
    assert body["address"]["province_id"] == 15
    assert "printer" not in body

    progress = [d for e, d in events if e == LABEL_PROGRESS]
    assert progress[0]["result"] == "success" and progress[0]["tracking_no"] == "79200000000001"
    done = [d for e, d in events if e == LABEL_DONE]
    assert done[0]["ok"] == 1


async def test_printer_setting_is_sent(engine, tmp_path, clock):
    env = LabelExecEnv(engine, tmp_path, clock,
                       [pt_ok(), fx("batch_fetch_tracking_nos")], printer_name="Printer A")
    oid = env.add_order(ORDER1)
    await execute(env, [oid])
    assert env.transport.requests[1]["json"]["printer"] == "Printer A"


async def test_biz_reject_marks_exception(engine, tmp_path, clock):
    env = LabelExecEnv(engine, tmp_path, clock,
                       [pt_ok(), fx("batch_fetch_partial_fail")])
    ok_id = env.add_order(ORDER1)
    bad_id = env.add_order(ORDER2)

    summary = await execute(env, [ok_id, bad_id])

    assert summary.ok == 1 and summary.failed == 1
    assert env.order(ok_id)["status"] == "label_obtained"
    bad = env.order(bad_id)
    assert bad["status"] == "exception"
    assert "超区" in bad["exception_reason"]
    assert env.task_by_key(f"label:1:{ORDER2}:1")["status"] == "failed"


async def test_whole_call_rejected_marks_all_exception(engine, tmp_path, clock):
    env = LabelExecEnv(engine, tmp_path, clock,
                       [pt_ok(), reply({"code": "602500705", "msg": "系统异常"})])
    oid = env.add_order(ORDER1)
    summary = await execute(env, [oid])
    assert summary.failed == 1
    assert env.order(oid)["status"] == "exception"
    assert "系统异常" in env.order(oid)["exception_reason"]


async def test_timeout_recovers_tracking_no(engine, tmp_path, clock):
    env = LabelExecEnv(engine, tmp_path, clock,
                       [pt_ok(), TransientError("timeout"), fx("get_order_logistics")])
    oid = env.add_order(ORDER1)
    events = collect_events(env)

    summary = await execute(env, [oid])

    assert summary.ok == 1
    assert env.waybills(oid)[0]["waybill_no"] == "79200000000001"
    assert env.order(oid)["status"] == "label_obtained"
    assert env.task_by_key(f"label:1:{ORDER1}:1")["status"] == "success"
    assert [d["result"] for e, d in events if e == LABEL_PROGRESS] == ["success"]


async def test_timeout_without_tracking_stays_verifying(engine, tmp_path, clock):
    env = LabelExecEnv(engine, tmp_path, clock, [
        pt_ok(), TransientError("timeout"),
        ok({"logistics": [], "logistics_list": []}),
    ])
    oid = env.add_order(ORDER1)
    events = collect_events(env)

    summary = await execute(env, [oid])

    assert summary.verifying == 1
    assert env.waybills(oid) == []
    assert env.order(oid)["status"] == "pending_label"
    assert env.task_by_key(f"label:1:{ORDER1}:1")["status"] == "verifying"
    assert [d["result"] for e, d in events if e == LABEL_PROGRESS] == ["verifying"]


async def test_not_found_label_msg_triggers_recovery(engine, tmp_path, clock):
    env = LabelExecEnv(engine, tmp_path, clock,
                       [pt_ok(), fx("batch_fetch_fail"), fx("get_order_logistics")])
    oid = env.add_order(ORDER1)
    summary = await execute(env, [oid])
    assert summary.ok == 1
    assert env.waybills(oid)[0]["waybill_no"] == "79200000000001"
    assert env.order(oid)["status"] == "label_obtained"


# ---- 打单并发货 ----

async def test_fetch_and_ship_sets_shipped(engine, tmp_path, clock):
    env = LabelExecEnv(engine, tmp_path, clock, [pt_ok(), fx("fetch_and_ship")])
    oid = env.add_order(ORDER3)
    summary = await execute(env, [oid], mode="fetch_and_ship")
    assert summary.ok == 1
    assert env.order(oid)["status"] == "shipped"
    assert env.waybills(oid)[0]["waybill_no"] == "79200000000002"
    assert env.transport.requests[1]["json"]["send_type"] == "3"


# ---- 执行前重新校验 ----

async def test_changed_order_is_skipped_without_requests(engine, tmp_path, clock):
    env = LabelExecEnv(engine, tmp_path, clock, [])
    oid = env.add_order(ORDER1)
    record = env.previews.preview_obtain([oid], {}, actor="admin")
    with engine.begin() as conn:
        conn.execute(sa.update(orders).where(orders.c.id == oid).values(
            status="shipped", platform_status=3))

    summary = await env.service.execute_inline(record.preview_id, "admin")

    assert summary.skipped == 1
    assert env.transport.requests == []


async def test_paused_shop_fails_without_requests(engine, tmp_path, clock):
    env = LabelExecEnv(engine, tmp_path, clock, [])
    oid = env.add_order(ORDER1)
    record = env.previews.preview_obtain([oid], {}, actor="admin")
    with engine.begin() as conn:
        shop_store.set_paused(conn, env.shop_id, "risk_blocked:602502151", "2026-11-25T00:00:00Z")

    summary = await env.service.execute_inline(record.preview_id, "admin")

    assert summary.failed == 1
    assert env.transport.requests == []


# ---- 演练模式 ----

async def test_dry_run_blocks_execute(engine, tmp_path, clock):
    env = LabelExecEnv(engine, tmp_path, clock, [], dry_run=True)
    oid = env.add_order(ORDER1)
    record = env.previews.preview_obtain([oid], {}, actor="admin")
    with pytest.raises(DryRunBlocked):
        await env.service.execute_inline(record.preview_id, "admin")
    assert env.transport.requests == []


# ---- 作废与重新取号 ----

async def test_void_then_reobtain_uses_next_seq(engine, tmp_path, clock):
    refetch = json.loads((WRITE / "batch_fetch_tracking_nos.json").read_text(encoding="utf-8"))
    refetch["data"]["success_list"][0]["tracking_no"] = "79200000000005"
    env = LabelExecEnv(engine, tmp_path, clock, [
        fx("cancel_tracking_nos"), pt_ok(), TransportResponse(200, json.dumps(refetch).encode()),
    ])
    oid = env.add_order(ORDER1, status="label_obtained")
    env.add_waybill(oid, waybill_no="79200000000001")

    record = env.previews.preview_void([oid], actor="admin")
    summary = await env.service.execute_inline(record.preview_id, "admin")
    assert summary.ok == 1
    assert env.waybills(oid)[0]["status"] == "void"
    assert env.order(oid)["status"] == "pending_label"

    summary2 = await execute(env, [oid])
    assert summary2.ok == 1
    waybills = env.waybills(oid)
    assert [w["seq"] for w in waybills] == [1, 2]
    assert waybills[1]["status"] == "active"
    assert env.task_by_key(f"label:1:{ORDER1}:2")["status"] == "success"


async def test_preview_after_success_blocks_repeat(engine, tmp_path, clock):
    env = LabelExecEnv(engine, tmp_path, clock, [pt_ok(), fx("batch_fetch_tracking_nos")])
    oid = env.add_order(ORDER1)
    await execute(env, [oid])

    record = env.previews.preview_obtain([oid], {}, actor="admin")
    view = env.previews.view(record)
    assert view["total_ready"] == 0
    assert "面单" in view["blocked"][0]["reason"]
