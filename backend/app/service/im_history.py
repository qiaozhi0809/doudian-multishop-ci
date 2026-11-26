"""飞鸽消息的读回、落库与过期删除。正文只经这里进出 im_message 表，不进日志。"""

import asyncio
from dataclasses import asdict, fields
from datetime import UTC, datetime

import structlog
from sqlalchemy import Engine

from app.adapter.flybird.parse import Message
from app.domain.im_rules import MESSAGE_RETENTION
from app.store import im_message_store

log = structlog.get_logger()

_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def load_since(engine: Engine, shop_id: int, since: str) -> list[Message]:
    """该店 since 之后的消息，按发送时间正序。"""
    with engine.connect() as conn:
        rows = im_message_store.recent_for_shop(conn, shop_id, since)
    names = [f.name for f in fields(Message)]
    return [Message(**{name: row[name] for name in names}) for row in rows]


def purge(engine: Engine, now: datetime) -> int:
    """删除保存超过保留期的消息，返回删除条数。"""
    cutoff = (now.astimezone(UTC) - MESSAGE_RETENTION).strftime(_ISO_FMT)
    with engine.begin() as conn:
        return im_message_store.purge_before(conn, cutoff)


async def save(engine: Engine, shop_id: int, msgs: list[Message], captured_at: str) -> None:
    """写失败不抛出（接收照常），只记条数与异常类型：异常信息里带 SQL 参数，即消息正文。"""
    rows = [asdict(m) for m in msgs]

    def insert() -> None:
        with engine.begin() as conn:
            im_message_store.insert_ignore(conn, shop_id, rows, captured_at)

    try:
        await asyncio.to_thread(insert)
    except Exception as e:  # noqa: BLE001
        log.warning("im.save_failed", shop_id=shop_id, count=len(rows), error=type(e).__name__)
