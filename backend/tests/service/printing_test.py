"""M3 打印编排（flows 7.4 / 10）：组件直连、补打数据、失败重试与手动降级。"""

import pytest

from app.adapter.doudian.errors import TransientError
from app.adapter.print.protocol import PrintOutcome
from app.domain.errors import InvalidRequest, NotFound
from app.domain.print_status import PrintJobStatus
from app.service.background import TaskAlreadyRunning
from app.service.events import PRINT_DONE, PRINT_PROGRESS
from app.service.printing import PrintSummary
from app.store import shop_store
from tests.service.print_support import FakeComponent, PrintEnv, info, infos
from tests.service.support import audit_rows

W1 = "79200000000001"
W2 = "79200000000002"


def collect(env):
    events: list[tuple[str, dict]] = []
    original = env.events.publish

    def recording(event, data):
        events.append((event, data))
        original(event, data)

    env.events.publish = recording
    return events


async def test_print_success_marks_waybill_and_order_printed(engine, tmp_path, clock):
    env = PrintEnv(engine, tmp_path, clock,
                   [infos(info(W1, template_url="https://t/x.xml", OAuth="oauth=1"))])
    oid = env.add_order()
    wid = env.add_waybill(oid)
    events = collect(env)

    summary = await env.service.run_inline([wid], "admin")

    assert summary == PrintSummary(ok=1, failed=0, manual=0, skipped=0)
    waybill = env.waybill(wid)
    assert waybill["status"] == "printed" and waybill["printed_at"]
    assert env.order(oid)["status"] == "printed"
    job = env.latest_jobs([wid])[wid]
    assert job["status"] == PrintJobStatus.SUCCESS.value and job["attempts"] == 1
    printer, documents = env.component.print_calls[0]
    assert printer == "Printer A"
    assert documents[0].waybill_no == W1
    assert documents[0].print_data == "PD"
    assert documents[0].template_url == "https://t/x.xml"
    assert documents[0].params == "oauth=1"
    assert any(e == PRINT_PROGRESS for e, _ in events)
    assert any(e == PRINT_DONE for e, _ in events)


async def test_recovered_waybill_backfills_print_data(engine, tmp_path, clock):
    env = PrintEnv(engine, tmp_path, clock, [
        infos(info(W1, print_data="FETCHED", sign="S2", template_url="T"))])
    oid = env.add_order()
    wid = env.add_waybill(oid, print_data=None, sign=None)

    summary = await env.service.run_inline([wid], "admin")

    assert summary.ok == 1
    waybill = env.waybill(wid)
    assert waybill["print_data"] == "FETCHED"
    assert waybill["sign"] == "S2"
    assert env.component.print_calls[0][1][0].print_data == "FETCHED"


async def test_no_print_data_anywhere_goes_manual(engine, tmp_path, clock):
    env = PrintEnv(engine, tmp_path, clock, [infos()])
    oid = env.add_order()
    wid = env.add_waybill(oid, print_data=None, sign=None)

    summary = await env.service.run_inline([wid], "admin")

    assert summary == PrintSummary(ok=0, failed=0, manual=1, skipped=0)
    job = env.latest_jobs([wid])[wid]
    assert job["status"] == PrintJobStatus.FAILED.value
    assert job["result_code"] == "no_print_data"
    assert "手动补打" in job["result_detail"]
    assert env.component.print_calls == []
    assert env.waybill(wid)["status"] == "active"
    assert env.order(oid)["status"] == "label_obtained"


async def test_component_failure_retries_once_then_manual_hint(engine, tmp_path, clock):
    component = FakeComponent(outcomes=[
        PrintOutcome(False, "component_failed", "打印机缺纸"),
        PrintOutcome(False, "component_failed", "打印机缺纸"),
    ])
    env = PrintEnv(engine, tmp_path, clock, [infos(info(W1))], component=component)
    oid = env.add_order()
    wid = env.add_waybill(oid)

    summary = await env.service.run_inline([wid], "admin")

    assert summary.failed == 1
    assert len(component.print_calls) == 2
    job = env.latest_jobs([wid])[wid]
    assert job["attempts"] == 2
    assert job["result_code"] == "component_failed"
    assert "打印机缺纸" in job["result_detail"]
    assert "手动补打" in job["result_detail"]
    assert env.order(oid)["status"] == "label_obtained"


async def test_component_retry_can_succeed(engine, tmp_path, clock):
    component = FakeComponent(outcomes=[
        PrintOutcome(False, "no_response", "超时"),
        PrintOutcome(True, "success", ""),
    ])
    env = PrintEnv(engine, tmp_path, clock, [infos(info(W1))], component=component)
    oid = env.add_order()
    wid = env.add_waybill(oid)

    summary = await env.service.run_inline([wid], "admin")

    assert summary.ok == 1
    assert len(component.print_calls) == 2
    assert env.latest_jobs([wid])[wid]["attempts"] == 2
    assert env.waybill(wid)["status"] == "printed"


async def test_component_unavailable_is_recorded(engine, tmp_path, clock):
    component = FakeComponent(outcomes=[
        PrintOutcome(False, "component_unavailable", "请先启动抖店官方打印组件"),
        PrintOutcome(False, "component_unavailable", "请先启动抖店官方打印组件"),
    ])
    env = PrintEnv(engine, tmp_path, clock, [infos(info(W1))], component=component)
    wid = env.add_waybill(env.add_order())

    summary = await env.service.run_inline([wid], "admin")

    assert summary.failed == 1
    assert env.latest_jobs([wid])[wid]["result_code"] == "component_unavailable"


async def test_no_component_at_all_is_rejected_before_jobs(engine, tmp_path, clock):
    env = PrintEnv(engine, tmp_path, clock, [], component=FakeComponent(available=False))
    wid = env.add_waybill(env.add_order())

    with pytest.raises(InvalidRequest):
        await env.service.run_inline([wid], "admin")

    assert env.latest_jobs([wid]) == {}
    assert env.transport.requests == []


async def test_print_infos_failure_degrades_to_stored_data(engine, tmp_path, clock):
    env = PrintEnv(engine, tmp_path, clock, [TransientError("timeout")])
    oid = env.add_order()
    wid = env.add_waybill(oid)

    summary = await env.service.run_inline([wid], "admin")

    assert summary.ok == 1
    assert env.component.print_calls[0][1][0].template_url is None
    assert env.waybill(wid)["status"] == "printed"


async def test_paused_shop_still_prints_with_stored_data(engine, tmp_path, clock):
    env = PrintEnv(engine, tmp_path, clock, [])
    oid = env.add_order()
    wid = env.add_waybill(oid)
    with engine.begin() as conn:
        shop_store.set_paused(conn, env.shop_id, "risk_blocked:602502151", "2026-11-25T00:00:00Z")

    summary = await env.service.run_inline([wid], "admin")

    assert summary.ok == 1
    assert env.transport.requests == []


async def test_prints_serially_in_input_order(engine, tmp_path, clock):
    env = PrintEnv(engine, tmp_path, clock, [infos(info(W1), info(W2))])
    oid1 = env.add_order("o1")
    oid2 = env.add_order("o2")
    wid1 = env.add_waybill(oid1, waybill_no=W1)
    wid2 = env.add_waybill(oid2, waybill_no=W2)

    summary = await env.service.run_inline([wid1, wid2], "admin")

    assert summary.ok == 2
    assert [docs[0].waybill_no for _, docs in env.component.print_calls] == [W1, W2]


async def test_void_waybill_is_rejected(engine, tmp_path, clock):
    env = PrintEnv(engine, tmp_path, clock, [])
    wid = env.add_waybill(env.add_order(), status="void")
    with pytest.raises(InvalidRequest):
        await env.service.run_inline([wid], "admin")


async def test_unknown_waybill_is_not_found(engine, tmp_path, clock):
    env = PrintEnv(engine, tmp_path, clock, [])
    with pytest.raises(NotFound):
        await env.service.run_inline([999], "admin")


async def test_reprint_printed_waybill_is_allowed(engine, tmp_path, clock):
    env = PrintEnv(engine, tmp_path, clock, [infos(info(W1))])
    wid = env.add_waybill(env.add_order(), status="printed")
    summary = await env.service.run_inline([wid], "admin")
    assert summary.ok == 1
    assert env.latest_jobs([wid])[wid]["status"] == "success"


async def test_dry_run_records_without_any_call(engine, tmp_path, clock):
    """演练模式：不探测组件、不取补打数据、不写 print_job，只写审计。"""
    env = PrintEnv(engine, tmp_path, clock, [], dry_run=True)
    wid = env.add_waybill(env.add_order())

    summary = await env.service.run_inline([wid], "admin")

    assert summary == PrintSummary(ok=0, failed=0, manual=0, skipped=1)
    assert env.component.probe_calls == 0
    assert env.component.print_calls == []
    assert env.transport.requests == []
    assert env.latest_jobs([wid]) == {}
    assert env.waybill(wid)["status"] == "active"  # 没有被标记已打印
    audit = [r for r in audit_rows(engine) if r["action"] == "dry_run_print_local"]
    assert audit and audit[0]["req_summary"]["waybill_no"] == W1


async def test_explicit_printer_name_wins(engine, tmp_path, clock):
    env = PrintEnv(engine, tmp_path, clock, [infos(info(W1))])
    wid = env.add_waybill(env.add_order())
    await env.service.run_inline([wid], "admin", printer_name="XP-58")
    assert env.component.print_calls[0][0] == "XP-58"
    assert env.latest_jobs([wid])[wid]["printer_name"] == "XP-58"


async def test_second_submit_is_rejected_while_batch_running(engine, tmp_path, clock):
    import asyncio

    from app.service.background import TaskRegistry

    tasks = TaskRegistry()
    env = PrintEnv(engine, tmp_path, clock, [infos(info(W1))], tasks=tasks)
    wid = env.add_waybill(env.add_order())
    gate = asyncio.Event()
    tasks.spawn("print-jobs", gate.wait())
    try:
        with pytest.raises(TaskAlreadyRunning):
            await env.service.submit([wid], "admin")
        assert env.latest_jobs([wid]) == {}
    finally:
        gate.set()
        await tasks.shutdown()


async def test_status_reports_component_state(engine, tmp_path, clock):
    env = PrintEnv(engine, tmp_path, clock, [], component=FakeComponent(available=False))
    status = await env.service.status()
    assert status["available"] is False
    assert status["printers"] == []
    assert status["error"]
    assert status["checked_at"]
