import json
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.adapter.doudian.errors import SessionExpired
from app.service.order_sync import OrderSyncService
from app.shared.logging_setup import configure_logging
from tests.fakes import ok, reply
from tests.service.support import Env

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "doudian"


def fx(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def order_no(i: int) -> str:
    return f"69{i:017d}"


def page_of(start: int, n: int, status: int = 2):
    """n 条待发货订单的 searchlist 响应。"""
    body = fx("searchlist_stock_up")
    template = body["data"][0]
    orders = []
    for i in range(start, start + n):
        o = json.loads(json.dumps(template))
        o["shop_order_id"] = order_no(i)
        o["order_status"] = status
        o["product_item"][0]["item_order_id"] = order_no(i)
        orders.append(o)
    body["data"] = orders
    return reply(body)


def by_order_id(no: int, status: int):
    resp = page_of(no, 1, status=status)
    return resp


def empty_page():
    return reply(fx("searchlist_stock_up_empty"))


@pytest.fixture
def env(engine, tmp_path):
    return Env(engine, tmp_path, responses=[])


def service(env, **kw) -> OrderSyncService:
    return OrderSyncService(env.engine, env.runner, env.sessions, env.events, **kw)


def db_orders(env) -> dict[str, tuple[str, int]]:
    with env.engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT order_no, status, platform_status FROM orders"))
        return {r.order_no: (r.status, r.platform_status) for r in rows}


def query(env, i: int) -> dict:
    return env.transport.requests[i]["params"]


async def test_paginates_until_short_page(env):
    env.transport.responses[:] = [page_of(0, 200), page_of(200, 200), page_of(400, 37)]
    result = await service(env).sync_pending(env.shop_id, "admin")
    assert (result.fetched, result.upserted, result.complete) == (437, 437, True)
    assert [query(env, i)["page"] for i in range(3)] == [0, 1, 2]
    p = query(env, 0)
    assert (p["tab"], p["order_status"], p["scene"], p["pageSize"]) == (
        "stock_up", "stock_up", 1, 200)
    assert len(db_orders(env)) == 437


async def test_exact_multiple_of_page_size(env):
    env.transport.responses[:] = [page_of(0, 200), empty_page()]
    result = await service(env).sync_pending(env.shop_id, "admin")
    assert result.fetched == 200 and len(env.transport.requests) == 2


async def test_session_expired_mid_pagination(env):
    env.transport.responses[:] = [page_of(0, 200), ok(code=10008)]
    with pytest.raises(SessionExpired):
        await service(env).sync_pending(env.shop_id, "admin")
    assert len(db_orders(env)) == 200  # 第 1 页已入库
    assert env.shop()["status"] == "needs_login"


async def test_vanished_closed_becomes_cancelled(env):
    svc = service(env)
    env.transport.responses[:] = [page_of(0, 2)]
    await svc.sync_pending(env.shop_id, "admin")
    env.transport.requests.clear()
    # 第二轮：待发货里只剩 0 号；1 号按单号补查得到已关闭
    env.transport.responses[:] = [page_of(0, 1), by_order_id(1, status=4)]
    result = await svc.sync_pending(env.shop_id, "admin")
    assert (result.rechecked, result.cancelled) == (1, 1)
    lookup = query(env, 1)
    assert (lookup["tab"], lookup["order_status"], lookup["order_id"]) == (
        "all", "", order_no(1))
    assert db_orders(env)[order_no(1)] == ("cancelled", 4)
    assert db_orders(env)[order_no(0)] == ("synced", 2)


async def test_vanished_shipped_not_rechecked_again(env):
    svc = service(env)
    env.transport.responses[:] = [page_of(0, 1)]
    await svc.sync_pending(env.shop_id, "admin")
    env.transport.responses[:] = [empty_page(), by_order_id(0, status=3)]
    result = await svc.sync_pending(env.shop_id, "admin")
    assert (result.rechecked, result.cancelled) == (1, 0)
    assert db_orders(env)[order_no(0)] == ("synced", 3)  # 只更新平台状态
    env.transport.requests.clear()
    env.transport.responses[:] = [empty_page()]
    result = await svc.sync_pending(env.shop_id, "admin")
    assert result.rechecked == 0 and len(env.transport.requests) == 1


async def test_recheck_not_found_marked_exception_and_not_retried(env, capsys):
    configure_logging(json=True)
    svc = service(env)
    env.transport.responses[:] = [page_of(0, 1)]
    await svc.sync_pending(env.shop_id, "admin")
    env.transport.responses[:] = [empty_page(), empty_page()]
    result = await svc.sync_pending(env.shop_id, "admin")
    assert (result.rechecked, result.cancelled) == (1, 0)
    with env.engine.connect() as conn:
        row = conn.execute(sa.text("SELECT status, exception_reason FROM orders")).one()
    assert tuple(row) == ("exception", "平台查不到该订单")
    log_out = capsys.readouterr().out
    assert "recheck_not_found" in log_out and order_no(0) in log_out
    env.transport.requests.clear()
    env.transport.responses[:] = [empty_page()]
    result = await svc.sync_pending(env.shop_id, "admin")
    assert result.rechecked == 0 and len(env.transport.requests) == 1  # 不再补查


async def test_recheck_capped_per_run(env):
    svc = service(env)
    env.transport.responses[:] = [page_of(0, 60)]
    await svc.sync_pending(env.shop_id, "admin")
    with env.engine.begin() as conn:  # 59 号最久没同步，应排在最前
        conn.execute(sa.text("UPDATE orders SET synced_at='2020-01-01T00:00:00Z' "
                             "WHERE order_no = :n"), {"n": order_no(59)})
    env.transport.requests.clear()
    env.transport.responses[:] = [empty_page()] + [by_order_id(i, 3) for i in range(60)]
    result = await svc.sync_pending(env.shop_id, "admin")
    assert result.rechecked == 50 and len(env.transport.requests) == 51
    assert query(env, 1)["order_id"] == order_no(59)
    # 剩下 10 单留到下一轮
    env.transport.requests.clear()
    env.transport.responses[:] = [empty_page()] + [by_order_id(i, 3) for i in range(10)]
    result = await svc.sync_pending(env.shop_id, "admin")
    assert result.rechecked == 10


async def test_incomplete_pagination_skips_recheck(env):
    svc = service(env, max_pages=2)
    env.transport.responses[:] = [page_of(0, 1)]
    await svc.sync_pending(env.shop_id, "admin")
    env.transport.requests.clear()
    env.transport.responses[:] = [page_of(100, 200), page_of(300, 200)]
    result = await svc.sync_pending(env.shop_id, "admin")
    assert result.complete is False and result.rechecked == 0
    assert len(env.transport.requests) == 2  # 没有补查请求


async def test_publishes_progress_per_page(env):
    sub = env.events.subscribe()
    env.transport.responses[:] = [page_of(0, 200), page_of(200, 37)]
    await service(env).sync_pending(env.shop_id, "admin")
    first = await anext(sub)
    second = await anext(sub)
    assert first == ("sync_progress", {"shop_id": env.shop_id, "kind": "orders", "fetched": 200})
    assert second == ("sync_progress", {"shop_id": env.shop_id, "kind": "orders", "fetched": 237})


async def test_local_status_not_overwritten_by_resync(env):
    svc = service(env)
    env.transport.responses[:] = [page_of(0, 1)]
    await svc.sync_pending(env.shop_id, "admin")
    with env.engine.begin() as conn:
        conn.execute(sa.text("UPDATE orders SET status='pending_label'"))
    env.transport.responses[:] = [page_of(0, 1)]
    await svc.sync_pending(env.shop_id, "admin")
    assert db_orders(env)[order_no(0)][0] == "pending_label"


# ---- 新订单识别与基线（通知中心 6.3）----

def drain(sub, name: str) -> list[dict]:
    out = []
    while not sub._queue.empty():
        event, data = sub._queue.get_nowait()
        if event == name:
            out.append(data)
    return out


def has_baseline(env, kind: str) -> bool:
    with env.engine.connect() as conn:
        return conn.execute(sa.text(
            "SELECT 1 FROM sync_baseline WHERE shop_id = :s AND kind = :k"
        ), {"s": env.shop_id, "k": kind}).first() is not None


async def test_first_sync_establishes_baseline_then_new_orders_notify(env):
    svc = service(env)
    sub = env.events.subscribe()
    env.transport.responses[:] = [page_of(0, 30)]
    await svc.sync_pending(env.shop_id, "admin")
    assert drain(sub, "orders_new") == []  # 首次只入库不提醒
    assert has_baseline(env, "orders")

    env.transport.responses[:] = [page_of(0, 31)]
    await svc.sync_pending(env.shop_id, "admin")
    assert drain(sub, "orders_new") == [{"shop_id": env.shop_id, "count": 1}]

    env.transport.responses[:] = [page_of(0, 31)]
    await svc.sync_pending(env.shop_id, "admin")
    assert drain(sub, "orders_new") == []  # 没有新单不发


async def test_empty_first_sync_still_establishes_baseline(env):
    env.transport.responses[:] = [empty_page()]
    await service(env).sync_pending(env.shop_id, "admin")
    assert has_baseline(env, "orders")


async def test_incomplete_sync_no_baseline_no_event(env):
    svc = service(env, max_pages=2)
    sub = env.events.subscribe()
    env.transport.responses[:] = [page_of(0, 200), page_of(200, 200)]
    result = await svc.sync_pending(env.shop_id, "admin")
    assert result.complete is False
    assert not has_baseline(env, "orders")
    assert drain(sub, "orders_new") == []


async def test_failed_sync_with_baseline_does_not_notify(env):
    svc = service(env)
    env.transport.responses[:] = [page_of(0, 1)]
    await svc.sync_pending(env.shop_id, "admin")
    sub = env.events.subscribe()
    env.transport.responses[:] = [page_of(100, 200), ok(code=10008)]
    with pytest.raises(SessionExpired):
        await svc.sync_pending(env.shop_id, "admin")
    assert drain(sub, "orders_new") == []
