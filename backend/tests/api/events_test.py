import asyncio

from app.api.event import event_stream, format_event
from app.service.events import EventBus


async def _never_disconnected() -> bool:
    return False


async def test_sse_receives_status_change():
    bus = EventBus()
    stream = event_stream(bus.subscribe(), _never_disconnected, heartbeat_s=5)
    assert await anext(stream) == ": connected\n\n"
    bus.publish("shop_status_changed", {"shop_id": 1, "status": "needs_login"})
    chunk = await asyncio.wait_for(anext(stream), 1)
    assert chunk == format_event("shop_status_changed", {"shop_id": 1, "status": "needs_login"})
    assert chunk.startswith("event: shop_status_changed\ndata: {")
    assert chunk.endswith("\n\n")
    await stream.aclose()


async def test_idle_stream_sends_heartbeat():
    bus = EventBus()
    stream = event_stream(bus.subscribe(), _never_disconnected, heartbeat_s=0.01)
    await anext(stream)
    assert await asyncio.wait_for(anext(stream), 1) == ": ping\n\n"
    await stream.aclose()


async def test_disconnect_unsubscribes():
    bus = EventBus()
    states = iter([False, True])

    async def is_disconnected() -> bool:
        return next(states)

    stream = event_stream(bus.subscribe(), is_disconnected, heartbeat_s=0.01)
    assert [c async for c in stream][0] == ": connected\n\n"
    assert bus.subscriber_count == 0


async def test_closing_stream_unsubscribes():
    bus = EventBus()
    stream = event_stream(bus.subscribe(), _never_disconnected, heartbeat_s=5)
    await anext(stream)
    assert bus.subscriber_count == 1
    await stream.aclose()
    assert bus.subscriber_count == 0


def test_format_keeps_chinese_readable():
    assert "扫码登录取消" in format_event("shop_login_failed", {"reason": "扫码登录取消"})
