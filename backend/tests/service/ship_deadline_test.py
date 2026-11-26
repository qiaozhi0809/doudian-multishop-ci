"""ENG-07：临近发货超时告警（只读本地订单，SSE 推送）。"""

import sqlalchemy as sa

from app.service.events import SHIP_DEADLINE_WARNING, EventBus
from app.service.ship_deadline import ShipDeadlineWatcher
from app.store.schema import orders
from tests.service.label_support import add_order, add_shop


def _seed(engine, shop_id, order_no, *, status="printed", exp_ship_time):
    order_id = add_order(engine, shop_id, order_no, status=status)
    with engine.begin() as conn:
        conn.execute(sa.update(orders).where(orders.c.id == order_id).values(
            exp_ship_time=exp_ship_time))
    return order_id


def _watcher(engine, clock, events, warn_hours=6):
    return ShipDeadlineWatcher(engine, events, warn_hours=warn_hours, clock=clock)


def test_due_orders_published(engine, clock):
    events = EventBus()
    shop_id = add_shop(engine)
    _seed(engine, shop_id, "o-soon", exp_ship_time="2026-12-01T03:00:00Z")  # 3h 后
    _seed(engine, shop_id, "o-late", exp_ship_time="2026-11-30T20:00:00Z")  # 已超时
    _seed(engine, shop_id, "o-far", exp_ship_time="2026-12-05T00:00:00Z")  # 5 天，不告警
    _seed(engine, shop_id, "o-done", status="shipped", exp_ship_time="2026-12-01T01:00:00Z")
    _seed(engine, shop_id, "o-none", exp_ship_time=None)
    published: list[dict] = []
    original = events.publish

    def record(event, data):
        if event == SHIP_DEADLINE_WARNING:
            published.append(data)
        original(event, data)

    events.publish = record

    result = _watcher(engine, clock, events).scan()

    assert result["count"] == 2
    assert [i["order_no"] for i in result["items"]] == ["o-late", "o-soon"]
    assert published[0]["count"] == 2 and published[0]["warn_hours"] == 6
    assert published[0]["items"][0]["shop_name"] == "店A"


def test_zero_count_event_clears_reminder(engine, clock):
    """没有到期订单时也发一次数量为 0 的事件，界面据此移除旧提醒。"""
    events = EventBus()
    shop_id = add_shop(engine)
    _seed(engine, shop_id, "o-far", exp_ship_time="2026-12-05T00:00:00Z")
    published: list[dict] = []
    original = events.publish

    def record(event, data):
        if event == SHIP_DEADLINE_WARNING:
            published.append(data)
        original(event, data)

    events.publish = record

    assert _watcher(engine, clock, events).scan()["count"] == 0
    assert published == [{"count": 0, "warn_hours": 6, "checked_at": "2026-12-01T00:00:00Z",
                          "items": [], "shop_counts": {}}]


def test_warn_hours_is_configurable(engine, clock):
    events = EventBus()
    shop_id = add_shop(engine)
    _seed(engine, shop_id, "o-soon", exp_ship_time="2026-12-01T03:00:00Z")

    assert _watcher(engine, clock, events, warn_hours=12).scan()["count"] == 1
    assert _watcher(engine, clock, events, warn_hours=1).scan()["count"] == 0


def test_shop_counts_not_capped_by_item_limit(engine, clock):
    events = EventBus()
    a, b = add_shop(engine, name="店A"), add_shop(engine, name="店B")
    for i in range(3):
        _seed(engine, a, f"a{i}", exp_ship_time=f"2026-11-30T2{i}:00:00Z")
    for i in range(2):
        _seed(engine, b, f"b{i}", exp_ship_time="2026-12-01T02:00:00Z")
    watcher = ShipDeadlineWatcher(engine, events, warn_hours=6, limit=2, clock=clock)
    sub = events.subscribe()
    watcher.scan()
    _event, data = sub._queue.get_nowait()
    assert len(data["items"]) == 2 and {i["shop_id"] for i in data["items"]} == {a}
    assert data["shop_counts"] == {a: 3, b: 2}
