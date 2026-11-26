import asyncio

from app.service.events import EventBus


async def test_event_bus_fanout():
    bus = EventBus()
    a, b = bus.subscribe(), bus.subscribe()
    bus.publish("shop_status_changed", {"shop_id": 1})
    bus.publish("sync_progress", {"shop_id": 1, "fetched": 3})
    for sub in (a, b):
        assert await asyncio.wait_for(anext(sub), 1) == ("shop_status_changed", {"shop_id": 1})
        assert (await asyncio.wait_for(anext(sub), 1))[0] == "sync_progress"


async def test_full_queue_drops_oldest():
    bus = EventBus(queue_size=3)
    sub = bus.subscribe()
    for i in range(5):
        bus.publish("e", {"i": i})
    got = [(await asyncio.wait_for(anext(sub), 1))[1]["i"] for _ in range(3)]
    assert got == [2, 3, 4]


async def test_slow_subscriber_does_not_block_publisher_or_others():
    bus = EventBus(queue_size=1)
    slow, fast = bus.subscribe(), bus.subscribe()
    for i in range(3):
        bus.publish("e", {"i": i})
        assert (await anext(fast))[1]["i"] == i
    assert (await anext(slow))[1]["i"] == 2


async def test_close_unsubscribes():
    bus = EventBus()
    sub = bus.subscribe()
    sub.close()
    bus.publish("e", {})
    assert bus.subscriber_count == 0


async def test_async_with_unsubscribes():
    bus = EventBus()
    async with bus.subscribe() as sub:
        assert bus.subscriber_count == 1
        bus.publish("e", {"x": 1})
        assert await anext(sub) == ("e", {"x": 1})
    assert bus.subscriber_count == 0


async def test_publish_from_thread_wakes_subscriber():
    bus = EventBus()
    sub = bus.subscribe()
    waiter = asyncio.ensure_future(anext(sub))  # 订阅者先进入等待
    await asyncio.sleep(0)
    await asyncio.to_thread(bus.publish, "shop_status_changed", {"shop_id": 1})
    assert await asyncio.wait_for(waiter, 1) == ("shop_status_changed", {"shop_id": 1})


def test_publish_with_closed_loop_subscriber_is_ignored():
    bus = EventBus()
    loop = asyncio.new_event_loop()

    async def subscribe():
        return bus.subscribe()

    sub = loop.run_until_complete(subscribe())
    loop.close()
    bus.publish("e", {})  # 订阅者的循环已关闭：不抛异常
    sub.close()


def test_drop_logs_event_name(monkeypatch):
    from app.service import events as events_mod
    warned = []
    monkeypatch.setattr(events_mod.log, "warning", lambda msg, **kw: warned.append((msg, kw)))
    bus = events_mod.EventBus(queue_size=1)
    bus.subscribe()
    bus.publish("a", {"secret": "x"})
    bus.publish("b", {"secret": "y"})
    assert warned == [("events.dropped", {"dropped_event": "a"})]
