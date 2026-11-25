"""M4 发货服务：检查请求、幂等、成功 / 部分失败、重试、演练与店铺隔离。"""

from pathlib import Path

import pytest

from app.adapter.browser.login import LoginResult
from app.adapter.doudian.errors import TransientError
from app.adapter.doudian.transport import TransportResponse
from app.domain.errors import DryRunBlocked, InvalidRequest
from app.service.shipping_plan import group_packages, load_targets
from app.store import shipping_store
from tests.fakes import reply
from tests.service.label_support import add_address, add_shop
from tests.service.m4_support import NOW_ISO, M4Env, wait_until
from tests.service.support import TOKEN

M4 = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "m4"


def fx(name: str) -> TransportResponse:
    return TransportResponse(200, (M4 / f"{name}.json").read_bytes())


@pytest.fixture
def env(engine, tmp_path, clock):
    return M4Env(engine, tmp_path, clock, [])


def add_printed_order(env, order_no="6900000000000000001", waybill_no="79200000000001") -> int:
    oid = env.add_order(order_no, status="printed")
    env.add_waybill(oid, waybill_no=waybill_no)
    return oid


async def test_check_sends_verified_request(env):
    oid = add_printed_order(env)
    env.transport.responses.append(fx("sendcheck"))
    view = await env.shipping.check([oid], "admin")
    request = env.transport.requests[-1]
    assert request["url"].endswith("/api/order/sendcheck")
    assert request["json"]["orderIds"] == ["6900000000000000001"]
    assert request["json"]["checkType"] == 13
    assert request["json"]["address"]["mobile"] == "138****0000"
    assert view.shops[0].result.total == 1
    assert view.double_check_total == 0


async def test_ship_success_marks_shipped_and_audited(env):
    oid = add_printed_order(env)
    env.transport.responses.extend([fx("sendcheck"), fx("deliver_goods")])
    started = await env.shipping.ship([oid], "admin")
    await wait_until(lambda: env.order(oid)["status"] == "shipped")
    shipments = env.shipments(started.batch_id)
    assert [(s["status"], s["fail_msg"]) for s in shipments] == [("success", None)]
    task = env.task(f"ship:{env.shop_id}:zhongtong:79200000000001")
    assert task is not None and task["status"] == "success"
    deliver = [r for r in env.transport.requests
               if r["url"].endswith("/api/order/batchDeliverGoodsByEES")]
    assert deliver[0]["json"]["send_type"] == "3"
    assert deliver[0]["json"]["batch_deliver_packages"] == [
        {"logistics_company_code": "zhongtong", "tracking_no": "79200000000001"}]
    with env.engine.connect() as conn:
        actions = [r[0] for r in conn.exec_driver_sql(
            "SELECT action FROM audit_log ORDER BY id")]
    assert "ship_batch" in actions


async def test_double_check_requires_ack(env):
    oid = add_printed_order(env)
    env.transport.responses.append(fx("sendcheck_double"))
    with pytest.raises(InvalidRequest) as exc:
        await env.shipping.ship([oid], "admin")
    assert "二次确认" in str(exc.value)
    env.transport.responses.extend([fx("sendcheck_double"), fx("deliver_goods")])
    started = await env.shipping.ship([oid], "admin", double_check_ack=True)
    await wait_until(lambda: env.order(oid)["status"] == "shipped")
    assert env.shipments(started.batch_id)[0]["status"] == "success"


async def test_partial_failure_marks_each_order(env):
    first = add_printed_order(env, "6900000000000000001", "79200000000001")
    second = add_printed_order(env, "6900000000000000002", "79200000000002")
    env.transport.responses.extend([fx("sendcheck"), fx("deliver_partial")])
    started = await env.shipping.ship([first, second], "admin")
    await wait_until(
        lambda: all(s["status"] != "pending" for s in env.shipments(started.batch_id)))
    by_order = {s["order_id"]: s for s in env.shipments(started.batch_id)}
    assert by_order[first]["status"] == "success"
    assert by_order[second]["status"] == "failed"
    assert by_order[second]["fail_msg"] == "运单号已被使用"
    assert env.order(first)["status"] == "shipped"
    assert env.order(second)["status"] == "printed"  # 失败不推进本地状态
    assert env.task(
        f"ship:{env.shop_id}:zhongtong:79200000000002")["status"] == "failed"


async def test_transient_deliver_is_retried_then_succeeds(env):
    oid = add_printed_order(env)
    env.transport.responses.extend([
        fx("sendcheck"), TransientError("HTTP 503"), fx("deliver_goods")])
    started = await env.shipping.ship([oid], "admin")
    await wait_until(lambda: env.order(oid)["status"] == "shipped")
    assert env.shipments(started.batch_id)[0]["status"] == "success"
    deliver = [r for r in env.transport.requests
               if r["url"].endswith("/api/order/batchDeliverGoodsByEES")]
    assert len(deliver) == 2


async def test_deliver_exhausted_marks_unknown_result(env):
    oid = add_printed_order(env)
    env.transport.responses.extend([
        fx("sendcheck"),
        TransientError("HTTP 503"), TransientError("HTTP 503"), TransientError("HTTP 503"),
    ])
    started = await env.shipping.ship([oid], "admin")
    await wait_until(lambda: env.shipments(started.batch_id)[0]["status"] == "failed")
    assert "结果不明" in env.shipments(started.batch_id)[0]["fail_msg"]
    assert env.order(oid)["status"] == "printed"


async def test_blocked_orders_are_reported_not_shipped(env):
    oid = env.add_order("o1")  # pending_label，没有面单
    view = await env.shipping.check([oid], "admin")
    assert view.targets == ()
    assert "没有有效面单" in view.blocked[0].reason
    with pytest.raises(InvalidRequest):
        await env.shipping.ship([oid], "admin")


async def test_dry_run_blocks_ship(env):
    oid = add_printed_order(env)
    env.shipping._dry_run = True
    with pytest.raises(DryRunBlocked):
        await env.shipping.ship([oid], "admin")


def test_prepare_is_idempotent_when_shipment_exists(env):
    oid = add_printed_order(env)
    with env.engine.begin() as conn:
        shipping_store.insert_pending(conn, [{
            "shop_id": env.shop_id, "order_id": oid, "waybill_id": None,
            "courier_code": "zhongtong", "tracking_no": "79200000000001",
        }], "old-batch", NOW_ISO)
        shipping_store.finish_order(conn, "old-batch", oid, "success", None, NOW_ISO)
    targets, blocked = load_targets(env.engine, [oid])
    assert blocked == []
    outcome, task = env.shipping._prepare("new-batch", group_packages(targets)[0], "admin")
    assert outcome == "done" and task is None
    with env.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM tasks").scalar() == 0


async def test_one_shop_failure_does_not_block_other_shop(env):
    first = add_printed_order(env)
    shop_b = add_shop(env.engine, "店B")
    add_address(env.engine, shop_b)
    env.sessions.save_login(shop_b, LoginResult(
        [{"name": "sessionid", "value": "v2", "domain": ".jinritemai.com", "path": "/"}],
        TOKEN + "b", "2027-01-24T00:00:00Z", {"User-Agent": "UA/1"},
    ))
    second = env.add_order_for(shop_b, "6900000000000000009", status="printed")
    env.add_waybill_for(shop_b, second, waybill_no="79200000000009")
    env.transport.responses.extend([
        fx("sendcheck"),
        reply({"code": "602500705", "msg": "系统异常，请联系客服咨询"}, 200),
        fx("deliver_goods"),
    ])
    started = await env.shipping.ship([first, second], "admin")
    await wait_until(
        lambda: all(s["status"] != "pending" for s in env.shipments(started.batch_id)))
    by_order = {s["order_id"]: s for s in env.shipments(started.batch_id)}
    assert by_order[first]["status"] == "success"
    assert by_order[second]["status"] == "failed"
    assert "602500705" in by_order[second]["fail_msg"]
    assert env.order(first)["status"] == "shipped"


def test_pool_lists_shippable_orders(env):
    oid = add_printed_order(env)
    env.add_order("6900000000000000002", status="pending_label")
    rows, total = env.shipping.pool(None, 1, 50)
    assert total == 1
    assert rows[0]["id"] == oid and rows[0]["tracking_no"] == "79200000000001"
    assert rows[0]["printed"] is True


async def test_sendcheck_parse_double_detail(env):
    oid = add_printed_order(env)
    env.transport.responses.append(fx("sendcheck_double"))
    view = await env.shipping.check([oid], "admin")
    assert view.double_check_total == 1
    assert view.shops[0].result.double_check_detail[0]["title"] == "请确认发货信息"


async def test_batch_view_after_run(env):
    oid = add_printed_order(env)
    env.transport.responses.extend([fx("sendcheck"), fx("deliver_goods")])
    started = await env.shipping.ship([oid], "admin")
    await wait_until(lambda: env.order(oid)["status"] == "shipped")
    rows = env.shipping.batch(started.batch_id)
    assert len(rows) == 1 and rows[0]["tracking_no"] == "79200000000001"
