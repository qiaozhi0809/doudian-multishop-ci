import json
from pathlib import Path

import pytest

from app.adapter.doudian.errors import BizRejected
from app.service.aftersale import AftersaleService
from tests.fakes import reply
from tests.service.support import Env

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "m5"


def fx(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def env(engine, tmp_path):
    return Env(engine, tmp_path, responses=[])


def service(env) -> AftersaleService:
    return AftersaleService(env.engine, env.runner)


async def test_sync_stores_rows_and_list_reads_local(env):
    env.transport.responses[:] = [reply(fx("aftersale_list"))]
    (outcome,) = await service(env).sync([env.shop_id], "admin")
    assert (outcome.fetched, outcome.complete, outcome.error) == (2, True, None)
    assert outcome.synced_at is not None

    rows, total = service(env).list_local([env.shop_id])
    assert total == 2
    assert rows[0]["shop_name"] == "店A"
    assert rows[0]["after_sale_id"] == "140000000000000001"  # apply_time 较新，排在前
    assert rows[0]["display"]["status_text"] == "待商家处理"
    assert rows[1]["status_deadline"] is None

    todo, todo_total = service(env).list_local([env.shop_id], open_only=True, by_deadline=True)
    assert todo_total == 1
    assert todo[0]["after_sale_id"] == "140000000000000001"

    body = env.transport.requests[0]["json"]
    assert body["page"] == 1  # 售后列表 1-based
    assert body["conf_version"] == "v13"


async def test_sync_pages_only_when_full(env):
    body = fx("aftersale_list")
    template = body["data"]["items"][0]
    full = json.loads(json.dumps(body))
    full["data"]["items"] = [
        {**template, "after_sale_info": {**template["after_sale_info"],
                                         "after_sale_id": f"id{i}"}}
        for i in range(50)
    ]
    short = json.loads(json.dumps(body))
    short["data"]["items"] = [{**template, "after_sale_info": {
        **template["after_sale_info"], "after_sale_id": "last"}}]
    env.transport.responses[:] = [reply(full), reply(short)]

    (outcome,) = await service(env).sync([env.shop_id], "admin")
    assert (outcome.fetched, outcome.complete) == (51, True)
    assert [r["json"]["page"] for r in env.transport.requests] == [1, 2]


async def test_counts_upstream_and_failure_isolation(env):
    env.transport.responses[:] = [reply(fx("aftersale_counts"))]
    (result,) = await service(env).counts([env.shop_id], "admin")
    assert result.source == "upstream"
    assert result.pending_total == 2  # all_audit 1 + return_for_receive 1
    assert result.fetched_at is not None
    assert "all_audit" in env.transport.requests[0]["params"]["fields"]

    env.transport.responses[:] = [BizRejected("100021", "售后数据不可用")]
    (failed,) = await service(env).counts([env.shop_id], "admin")
    assert failed.source == "error"
    assert failed.counts is None
    assert failed.error and "售后数据不可用" in failed.error


async def test_detail_fetches_upstream(env):
    env.transport.responses[:] = [reply(fx("aftersale_detail"))]
    detail = await service(env).detail(env.shop_id, "140000000000000001", "admin")
    assert detail["title_info"]["title"] == "退货退款"
    assert len(detail["progress_node"]) == 2
    params = env.transport.requests[0]["params"]
    assert params["after_sale_id"] == "140000000000000001"
    assert params["aftersale_platform_source"] == "fxg"


# ---- 计数缓存（shop_cache）：每店 60 秒，只缓存成功结果，同步后失效 ----

class Clock:
    def __init__(self) -> None:
        from datetime import UTC, datetime
        self.now = datetime(2026, 11, 25, 8, 0, tzinfo=UTC)

    def __call__(self):
        return self.now

    def advance(self, seconds: int) -> None:
        from datetime import timedelta
        self.now += timedelta(seconds=seconds)


def counts_requests(env) -> int:
    return sum(1 for r in env.transport.requests if "fields" in (r.get("params") or {}))


async def test_counts_cached_per_shop_for_60_seconds(env):
    clock = Clock()
    svc = AftersaleService(env.engine, env.runner, clock=clock)
    env.transport.responses[:] = [reply(fx("aftersale_counts")), reply(fx("aftersale_counts"))]

    (first,) = await svc.counts([env.shop_id], "admin")
    clock.advance(59)
    (second,) = await svc.counts([env.shop_id], "admin")
    assert counts_requests(env) == 1  # 60 秒内不再请求平台
    assert second.fetched_at == first.fetched_at  # 显示当初取数的时间
    assert second.pending_total == first.pending_total

    clock.advance(2)
    (third,) = await svc.counts([env.shop_id], "admin")
    assert counts_requests(env) == 2
    assert third.fetched_at != first.fetched_at


async def test_counts_failure_not_cached(env):
    svc = AftersaleService(env.engine, env.runner, clock=Clock())
    env.transport.responses[:] = [
        BizRejected("100021", "售后数据不可用"), reply(fx("aftersale_counts")),
    ]
    (failed,) = await svc.counts([env.shop_id], "admin")
    (ok,) = await svc.counts([env.shop_id], "admin")
    assert (failed.source, ok.source) == ("error", "upstream")


async def test_sync_invalidates_counts_cache(env):
    svc = AftersaleService(env.engine, env.runner, clock=Clock())
    env.transport.responses[:] = [
        reply(fx("aftersale_counts")), reply(fx("aftersale_list")), reply(fx("aftersale_counts")),
    ]
    await svc.counts([env.shop_id], "admin")
    await svc.sync([env.shop_id], "admin")
    await svc.counts([env.shop_id], "admin")
    assert counts_requests(env) == 2  # 同步后马上重新取


# ---- 新售后识别、基线与定时检查（通知中心 6.3）----

def list_of(*items: tuple[str, int]) -> object:
    """(after_sale_id, status_deadline) → 售后列表响应；deadline 为 0 表示已完结。"""
    body = fx("aftersale_list")
    template = body["data"]["items"][0]
    body["data"]["items"] = [
        {**template, "after_sale_info": {
            **template["after_sale_info"], "after_sale_id": sid, "status_deadline": deadline}}
        for sid, deadline in items
    ]
    return reply(body)


def counts_with(all_audit: int, return_for_receive: int = 1) -> object:
    body = fx("aftersale_counts")
    body["data"]["all_audit"] = all_audit
    body["data"]["return_for_receive"] = return_for_receive
    return reply(body)


def list_requests(env) -> int:
    return sum(1 for r in env.transport.requests if r.get("json"))


def drain(sub, name: str) -> list[dict]:
    out = []
    while not sub._queue.empty():
        event, data = sub._queue.get_nowait()
        if event == name:
            out.append(data)
    return out


def has_baseline(env) -> bool:
    import sqlalchemy as sa
    with env.engine.connect() as conn:
        return conn.execute(sa.text(
            "SELECT 1 FROM sync_baseline WHERE shop_id = :s AND kind = 'aftersales'"
        ), {"s": env.shop_id}).first() is not None


OPEN = 1764600000


def checker(env, clock=None) -> AftersaleService:
    return AftersaleService(env.engine, env.runner, clock=clock or Clock(), events=env.events)


async def test_check_new_first_run_syncs_and_establishes_baseline(env):
    svc = checker(env)
    sub = env.events.subscribe()
    env.transport.responses[:] = [counts_with(1), list_of(("a1", OPEN))]
    assert await svc.check_new(env.shop_id) == 0  # 无基线：只入库不提醒
    assert list_requests(env) == 1 and has_baseline(env)
    assert drain(sub, "aftersales_new") == []


async def test_check_new_skips_list_when_count_unchanged(env):
    clock = Clock()
    svc = checker(env, clock)
    env.transport.responses[:] = [counts_with(1), list_of(("a1", OPEN))]
    await svc.check_new(env.shop_id)
    clock.advance(300)
    env.transport.requests.clear()
    env.transport.responses[:] = [counts_with(1)]
    assert await svc.check_new(env.shop_id) == 0
    assert (counts_requests(env), list_requests(env)) == (1, 0)


async def test_check_new_counts_only_new_todo(env):
    clock = Clock()
    svc = checker(env, clock)
    sub = env.events.subscribe()
    env.transport.responses[:] = [counts_with(1), list_of(("a1", OPEN))]
    await svc.check_new(env.shop_id)
    clock.advance(300)
    env.transport.responses[:] = [
        counts_with(2), list_of(("a1", OPEN), ("a2", OPEN), ("old-closed", 0)),
    ]
    assert await svc.check_new(env.shop_id) == 1  # 已完结的新单不计
    assert drain(sub, "aftersales_new") == [{"shop_id": env.shop_id, "count": 1}]


async def test_check_new_counts_failure_skips_sync(env):
    svc = checker(env)
    env.transport.responses[:] = [BizRejected("100021", "售后数据不可用")]
    assert await svc.check_new(env.shop_id) == 0
    assert list_requests(env) == 0


async def test_first_aftersale_after_empty_baseline_notifies(env):
    """有订单但从没有售后的店：首次同步 0 条也建基线，之后第一笔售后能提醒（手动同步同口径）。"""
    svc = checker(env)
    sub = env.events.subscribe()
    env.transport.responses[:] = [list_of()]
    await svc.sync([env.shop_id], "admin")
    assert has_baseline(env)
    env.transport.responses[:] = [list_of(("first", OPEN))]
    (outcome,) = await svc.sync([env.shop_id], "admin")
    assert outcome.new == 1
    assert drain(sub, "aftersales_new") == [{"shop_id": env.shop_id, "count": 1}]


async def test_incomplete_aftersale_sync_no_baseline(env):
    full = [(f"id{i}", OPEN) for i in range(50)]
    env.transport.responses[:] = [list_of(*full), BizRejected("100021", "售后数据不可用")]
    (outcome,) = await checker(env).sync([env.shop_id], "admin")
    assert outcome.error and not has_baseline(env)


async def test_check_new_syncs_when_breakdown_changes_with_same_total(env):
    """一单进待审核、一单离开待收货：合计不变但分组变了，也要同步。"""
    clock = Clock()
    svc = checker(env, clock)
    env.transport.responses[:] = [counts_with(1, 1), list_of(("a1", OPEN))]
    await svc.check_new(env.shop_id)
    clock.advance(300)
    env.transport.requests.clear()
    env.transport.responses[:] = [counts_with(2, 0), list_of(("a1", OPEN), ("a2", OPEN))]
    assert await svc.check_new(env.shop_id) == 1
    assert list_requests(env) == 1


async def test_check_new_forces_sync_on_sixth_unchanged_check(env):
    clock = Clock()
    svc = checker(env, clock)
    env.transport.responses[:] = [counts_with(1), list_of(("a1", OPEN))]
    await svc.check_new(env.shop_id)
    env.transport.requests.clear()
    for _ in range(5):
        clock.advance(300)
        env.transport.responses[:] = [counts_with(1)]
        await svc.check_new(env.shop_id)
    assert list_requests(env) == 0  # 前 5 轮没变：只取计数
    clock.advance(300)
    env.transport.responses[:] = [counts_with(1), list_of(("a1", OPEN), ("a2", OPEN))]
    assert await svc.check_new(env.shop_id) == 1  # 第 6 轮兜底同步
    assert list_requests(env) == 1
    clock.advance(300)
    env.transport.requests.clear()
    env.transport.responses[:] = [counts_with(1)]
    await svc.check_new(env.shop_id)
    assert list_requests(env) == 0  # 兜底后重新计数


async def test_partial_aftersale_sync_with_baseline_notifies_inserted(env):
    svc = checker(env)
    sub = env.events.subscribe()
    env.transport.responses[:] = [list_of()]
    await svc.sync([env.shop_id], "admin")
    full = [(f"id{i}", OPEN) for i in range(49)] + [("closed", 0)]
    env.transport.responses[:] = [list_of(*full), BizRejected("100021", "售后数据不可用")]
    (outcome,) = await svc.sync([env.shop_id], "admin")
    assert outcome.error
    assert drain(sub, "aftersales_new") == [{"shop_id": env.shop_id, "count": 49}]


async def test_prune_error_does_not_lose_new_aftersale_report(env, monkeypatch):
    from app.store import aftersale_store
    svc = checker(env)
    env.transport.responses[:] = [list_of()]
    await svc.sync([env.shop_id], "admin")
    sub = env.events.subscribe()

    def boom(*_a, **_k):
        raise RuntimeError("prune failed")

    monkeypatch.setattr(aftersale_store, "prune_unseen", boom)
    env.transport.responses[:] = [list_of(("n1", OPEN))]
    (outcome,) = await svc.sync([env.shop_id], "admin")
    assert outcome.error
    assert drain(sub, "aftersales_new") == [{"shop_id": env.shop_id, "count": 1}]


async def test_report_error_on_failed_sync_keeps_original_error(env, monkeypatch):
    from app.store import sync_baseline_store
    svc = checker(env)
    full = [(f"id{i}", OPEN) for i in range(50)]
    env.transport.responses[:] = [list_of(*full), BizRejected("100021", "售后数据不可用")]

    def boom(*_a, **_k):
        raise RuntimeError("report failed")

    monkeypatch.setattr(sync_baseline_store, "has", boom)
    (outcome,) = await svc.sync([env.shop_id], "admin")
    assert "售后数据不可用" in outcome.error


async def test_manual_sync_publishes_result_check_new_does_not(env):
    svc = checker(env)
    sub = env.events.subscribe()
    env.transport.responses[:] = [list_of(), BizRejected("100021", "售后数据不可用")]
    await svc.sync([env.shop_id], "admin")
    await svc.sync([env.shop_id], "admin")
    results = drain(sub, "sync_result")
    assert results[0] == {"kind": "aftersales", "shop_id": env.shop_id, "ok": True,
                          "error": None}
    assert results[1]["ok"] is False and "售后数据不可用" in results[1]["error"]

    env.transport.responses[:] = [counts_with(1), list_of(("a1", OPEN))]
    await svc.check_new(env.shop_id)
    assert drain(sub, "sync_result") == []
