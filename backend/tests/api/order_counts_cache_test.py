from datetime import timedelta

from tests.api.conftest import fx, tabcnt_ok
from tests.fakes import ok

TOKEN_A = "tok_" + "a" * 8


def counts_of(api, shop_id: int) -> dict:
    shops = api.client.get("/api/orders/counts").json()["shops"]
    return next(s for s in shops if s["shop_id"] == shop_id)


def test_counts_cached_60s(api, clock):
    sid = api.new_shop()
    api.login(sid, TOKEN_A)
    api.transport.queue(TOKEN_A, tabcnt_ok(stock_up=3))
    first = counts_of(api, sid)
    assert first["counts"]["stock_up"] == 3 and first["fetched_at"] == "2026-12-01T00:00:00Z"
    clock.now += timedelta(seconds=59)
    second = counts_of(api, sid)
    assert second == first and len(api.transport.requests) == 1  # 命中缓存，时间仍是取数时间
    clock.now += timedelta(seconds=2)  # 距取数 61 秒
    api.transport.queue(TOKEN_A, tabcnt_ok(stock_up=4))
    third = counts_of(api, sid)
    assert third["counts"]["stock_up"] == 4 and third["fetched_at"] == "2026-12-01T00:01:01Z"
    assert len(api.transport.requests) == 2


def test_failures_are_not_cached(api):
    sid = api.new_shop()
    api.login(sid, TOKEN_A)
    api.transport.queue(TOKEN_A, ok(code=602500705))
    assert counts_of(api, sid)["source"] == "error"
    assert counts_of(api, sid)["fetched_at"] is None
    api.transport.queue(TOKEN_A, tabcnt_ok(stock_up=1))
    assert counts_of(api, sid)["source"] == "upstream"


def test_cache_is_per_shop(api):
    a, b = api.new_shop("A", ip_n=5), api.new_shop("B", ip_n=6)
    api.login(a, TOKEN_A)
    api.login(b, "tok_" + "b" * 8)
    api.transport.queue(TOKEN_A, tabcnt_ok(stock_up=1))
    api.transport.queue("tok_" + "b" * 8, tabcnt_ok(stock_up=2))
    api.client.get("/api/orders/counts")
    api.client.get("/api/orders/counts")
    assert len(api.transport.requests) == 2  # 每店各一次


def test_counts_cache_invalidated_after_sync(api):
    sid = api.new_shop()
    api.login(sid, TOKEN_A)
    api.transport.queue(TOKEN_A, tabcnt_ok(stock_up=3))
    counts_of(api, sid)
    api.transport.queue(TOKEN_A, fx("searchlist_stock_up"))
    assert api.client.post("/api/orders/sync").status_code == 202
    api.wait_for(lambda: api.client.get("/api/orders").json()["total"] == 1)
    api.wait_for(lambda: len(api.transport.requests) == 2)
    api.wait_for(lambda: not api.app.state.tasks.is_running(f"orders-{sid}"))
    api.transport.queue(TOKEN_A, tabcnt_ok(stock_up=0))
    assert counts_of(api, sid)["counts"]["stock_up"] == 0  # 重新请求了，不是旧的 3
    assert len(api.transport.requests) == 3
