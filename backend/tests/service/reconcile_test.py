"""M4 对账服务：三类异常、同事务快照、窗口、first_seen、处理状态与店铺隔离。"""

import copy
import json
from pathlib import Path

import pytest

from app.adapter.browser.login import LoginResult
from app.adapter.doudian.errors import TransientError
from app.adapter.doudian.transport import TransportResponse
from app.domain.errors import InvalidRequest, NotFound
from app.domain.models import OrderFactDTO
from app.store import reconcile_store
from tests.service.label_support import add_address, add_shop
from tests.service.m4_support import NOW_ISO, M4Env, wait_until
from tests.service.support import TOKEN, FakeEgress

M4 = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "m4"


def facts() -> list[dict]:
    raw = (M4 / "searchlist_all.json").read_bytes()
    return json.loads(raw)["data"]


def searchlist(data: list[dict]) -> TransportResponse:
    body = json.dumps({"code": 0, "msg": "", "data": data}).encode()
    return TransportResponse(200, body)


@pytest.fixture
def env(engine, tmp_path, clock):
    return M4Env(engine, tmp_path, clock, [])


def seed_fact(env, order_no: str, status: int | None, tracking: str | None,
              first_seen: str = "2026-01-01T00:00:00Z") -> None:
    fact = OrderFactDTO(
        order_no=order_no, platform_status=status, user_id=None,
        create_time=NOW_ISO, pay_time=NOW_ISO, biz_date="2026-11-25",
        pay_amount_cents=None, goods_amount_cents=None, promotion_cents=None,
        post_cents=None, receive_amount_cents=None, exp_ship_time=None,
        ship_time=None, tracking_no=tracking, company_code="zhongtong", raw={},
    )
    with env.engine.begin() as conn:
        reconcile_store.upsert_facts(conn, env.shop_id, [fact], NOW_ISO)
        conn.execute(
            reconcile_store.order_fact.update().where(
                reconcile_store.order_fact.c.shop_id == env.shop_id,
                reconcile_store.order_fact.c.shop_order_id == order_no,
            ).values(first_seen_at=first_seen)
        )


def fact_row(env, order_no: str) -> dict:
    with env.engine.connect() as conn:
        row = conn.execute(
            reconcile_store.order_fact.select().where(
                reconcile_store.order_fact.c.shop_id == env.shop_id,
                reconcile_store.order_fact.c.shop_order_id == order_no,
            )
        ).mappings().first()
    assert row is not None
    return dict(row)


async def run_and_wait(env, *, window_days: int | None = None) -> str:
    started = await env.reconcile.run([env.shop_id], "admin", window_days)
    await wait_until(lambda: env.reconcile.latest_run()["status"] != "running")
    return started["run_id"]


async def test_first_run_builds_baseline_and_second_run_is_clean(env):
    data = facts()
    env.transport.responses.extend([searchlist(data), searchlist(copy.deepcopy(data))])
    first = await run_and_wait(env)
    findings = env.findings(first)
    assert len(findings) == 2  # 状态 3 与 5 各一条基线
    assert {f["kind"] for f in findings} == {"platform_shipped_local_not"}
    second = await run_and_wait(env)
    assert env.findings(second) == []


async def test_local_shipped_platform_not(env):
    seed_fact(env, "6900000000000000001", 3, "OLD-TRACKING")
    data = facts()
    data[0]["order_status"] = 2
    data[0]["latest_logistic_info"] = {"tracking_no": "", "company_code": ""}
    env.transport.responses.append(searchlist(data))
    run_id = await run_and_wait(env)
    finding = next(f for f in env.findings(run_id)
                   if f["shop_order_id"] == "6900000000000000001")
    assert finding["kind"] == "local_shipped_platform_not"
    assert finding["local_tracking_no"] == "OLD-TRACKING"


async def test_waybill_mismatch(env):
    seed_fact(env, "6900000000000000001", 3, "OLD-TRACKING")
    env.transport.responses.append(searchlist(facts()))
    run_id = await run_and_wait(env)
    finding = next(f for f in env.findings(run_id)
                   if f["shop_order_id"] == "6900000000000000001")
    assert finding["kind"] == "waybill_mismatch"
    assert finding["platform_tracking_no"] == "79200000000001"


async def test_window_filters_old_orders(env):
    data = facts()
    data[2]["create_time"] = 1780000000  # 2026-06，窗口外
    data[2]["pay_time"] = None
    env.transport.responses.append(searchlist(data))
    run_id = await run_and_wait(env, window_days=30)
    run = env.reconcile.latest_run()
    assert run["scanned"] == 2
    assert all(f["shop_order_id"] != "6900000000000000003"
               for f in env.findings(run_id))


async def test_first_seen_at_is_preserved(env):
    seed_fact(env, "6900000000000000001", 3, "79200000000001",
              first_seen="2026-01-01T00:00:00Z")
    env.transport.responses.append(searchlist(facts()))
    await run_and_wait(env)
    row = fact_row(env, "6900000000000000001")
    assert row["first_seen_at"] == "2026-01-01T00:00:00Z"
    assert row["synced_at"] != row["first_seen_at"]


async def test_findings_can_be_marked_handled(env):
    env.transport.responses.append(searchlist(facts()))
    await run_and_wait(env)
    finding = env.findings()[0]
    marked = env.reconcile.mark(finding["id"], "handled")
    assert marked["status"] == "handled" and marked["handled_at"] is not None
    assert env.reconcile.mark(finding["id"], "open")["status"] == "open"
    with pytest.raises(InvalidRequest):
        env.reconcile.mark(finding["id"], "bogus")
    with pytest.raises(NotFound):
        env.reconcile.mark(9999, "handled")


async def test_findings_query_filters_and_run_view(env):
    env.transport.responses.append(searchlist(facts()))
    run_id = await run_and_wait(env)
    items, total, run = env.reconcile.findings(
        [env.shop_id], run_id, "platform_shipped_local_not", "open", 1, 50)
    assert total == 2 and run["run_id"] == run_id
    assert all(i["kind_title"] for i in items)
    items, total, _ = env.reconcile.findings(
        [env.shop_id], run_id, "waybill_mismatch", None, 1, 50)
    assert total == 0


async def test_invalid_window_and_kind(env):
    with pytest.raises(InvalidRequest):
        await env.reconcile.run([env.shop_id], "admin", 0)
    with pytest.raises(InvalidRequest):
        env.reconcile.findings(None, None, "not-a-kind", None, 1, 50)
    with pytest.raises(NotFound):
        env.reconcile.findings(None, "missing-run", None, None, 1, 50)


class _SelectiveEgress(FakeEgress):
    def __init__(self, bad_shop_id: int) -> None:
        super().__init__()
        self.bad_shop_id = bad_shop_id

    async def ensure_ready(self, shop_id: int) -> None:
        await super().ensure_ready(shop_id)
        if shop_id == self.bad_shop_id:
            raise TransientError("出口不可用")


async def test_one_shop_failure_does_not_block_other_shop(env):
    shop_b = add_shop(env.engine, "店B")
    add_address(env.engine, shop_b)
    env.sessions.save_login(shop_b, LoginResult(
        [{"name": "sessionid", "value": "v2", "domain": ".jinritemai.com", "path": "/"}],
        TOKEN + "b", "2027-01-24T00:00:00Z", {"User-Agent": "UA/1"},
    ))
    env.runner._egress = _SelectiveEgress(bad_shop_id=shop_b)
    env.transport.responses.append(searchlist(facts()))
    started = await env.reconcile.run([env.shop_id, shop_b], "admin")
    await wait_until(lambda: env.reconcile.latest_run()["status"] != "running")
    run = env.reconcile.latest_run()
    assert run["status"] == "success"
    assert f"店铺 {shop_b}" in run["error"]
    assert len(env.findings(started["run_id"])) == 2
