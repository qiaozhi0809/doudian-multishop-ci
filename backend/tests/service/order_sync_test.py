import json
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.adapter.doudian.errors import SessionExpired
from app.service.order_sync import OrderSyncService
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


async def test_vanished_but_lookup_finds_nothing_is_left_alone(env):
    svc = service(env)
    env.transport.responses[:] = [page_of(0, 1)]
    await svc.sync_pending(env.shop_id, "admin")
    env.transport.responses[:] = [empty_page(), empty_page()]
    result = await svc.sync_pending(env.shop_id, "admin")
    assert (result.rechecked, result.cancelled) == (1, 0)
    assert db_orders(env)[order_no(0)] == ("synced", 2)


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
