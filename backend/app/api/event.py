"""SSE 推送。"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.service.events import Subscription

router = APIRouter(prefix="/api", tags=["events"])

HEARTBEAT_S = 15


def format_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def event_stream(
    sub: Subscription, is_disconnected: Callable[[], Awaitable[bool]],
    heartbeat_s: float = HEARTBEAT_S,
) -> AsyncIterator[str]:
    """把订阅到的事件转成 SSE 文本；空闲时发注释心跳，断开后取消订阅。"""
    try:
        yield ": connected\n\n"
        while not await is_disconnected():
            try:
                event, data = await asyncio.wait_for(anext(sub), heartbeat_s)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            yield format_event(event, data)
    finally:
        sub.close()


@router.get("/events")
async def events(request: Request) -> StreamingResponse:
    sub = request.app.state.events.subscribe()
    return StreamingResponse(
        event_stream(sub, request.is_disconnected),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
