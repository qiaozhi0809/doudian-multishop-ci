"""im_message 表读写。无业务判断（保留天数、等待计时由服务层决定）。"""

from collections.abc import Mapping, Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.store.im_schema import im_message as m

_CHUNK_ROWS = 500  # 单条 INSERT 的行数上限，避免超出 SQLite 绑定参数限制


def insert_ignore(
    conn: sa.Connection, shop_id: int, rows: Sequence[Mapping[str, str]], captured_at: str
) -> int:
    """rows 含 conversation_id / message_id / sender_role / text / sent_at。

    同一店铺已有的 message_id 跳过（保留首次记录）；返回新增条数。
    """
    values = [{**row, "shop_id": shop_id, "captured_at": captured_at} for row in rows]
    inserted = 0
    for start in range(0, len(values), _CHUNK_ROWS):
        stmt = sqlite_insert(m).values(values[start:start + _CHUNK_ROWS])
        inserted += conn.execute(stmt.on_conflict_do_nothing()).rowcount
    return inserted


def list_for_conversation(
    conn: sa.Connection, shop_id: int, conversation_id: str, *, limit: int = 200
) -> list[dict[str, Any]]:
    """该会话最近 limit 条，按 sent_at 正序返回。"""
    rows = conn.execute(
        sa.select(m)
        .where(m.c.shop_id == shop_id, m.c.conversation_id == conversation_id)
        .order_by(m.c.sent_at.desc(), m.c.id.desc())
        .limit(limit)
    ).mappings().all()
    return [dict(r) for r in reversed(rows)]


def recent_for_shop(conn: sa.Connection, shop_id: int, since: str) -> list[dict[str, Any]]:
    """该店发送时间不早于 since 的消息，按 sent_at 正序。"""
    rows = conn.execute(
        sa.select(m)
        .where(m.c.shop_id == shop_id, m.c.sent_at >= since)
        .order_by(m.c.sent_at, m.c.id)
    ).mappings().all()
    return [dict(r) for r in rows]


def purge_before(conn: sa.Connection, cutoff: str) -> int:
    """删除 captured_at 早于 cutoff 的消息，返回删除条数。"""
    res = conn.execute(sa.delete(m).where(m.c.captured_at < cutoff))
    return int(res.rowcount)
