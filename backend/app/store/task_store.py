"""tasks 读写与幂等键复用（backend 5.11）：success 不重跑，failed 复用行 attempts+1。"""

import json
from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa

from app.domain.task_status import TaskStatus
from app.store.schema import tasks


def get_by_key(conn: sa.Connection, key: str) -> Mapping[str, Any] | None:
    row = conn.execute(
        sa.select(tasks).where(tasks.c.idempotency_key == key)
    ).mappings().first()
    return dict(row) if row else None


def start(
    conn: sa.Connection, *, key: str, shop_id: int | None, type: str,
    payload: Mapping[str, Any], actor: str, now: str,
) -> Mapping[str, Any]:
    """返回该幂等键对应的任务行；已 success 的原样返回，其余置为 running。"""
    existing = get_by_key(conn, key)
    body = json.dumps(dict(payload), ensure_ascii=False)
    if existing is None:
        task_id = conn.execute(sa.insert(tasks).values(
            shop_id=shop_id, type=type, payload=body, idempotency_key=key,
            created_by=actor, status=TaskStatus.RUNNING.value, attempts=1,
            created_at=now, started_at=now,
        )).inserted_primary_key[0]
    elif existing["status"] in (
        TaskStatus.SUCCESS.value, TaskStatus.RUNNING.value, TaskStatus.QUEUED.value
    ):
        return existing  # 已成功不重跑；运行 / 排队中不重复计数
    else:  # failed / verifying / cancelled：复用行重试
        task_id = existing["id"]
        conn.execute(sa.update(tasks).where(tasks.c.id == task_id).values(
            status=TaskStatus.RUNNING.value, attempts=existing["attempts"] + 1,
            payload=body, started_at=now, finished_at=None, last_error=None,
        ))
    row = conn.execute(sa.select(tasks).where(tasks.c.id == task_id)).mappings().first()
    assert row is not None
    return dict(row)


def finish(
    conn: sa.Connection, task_id: int, status: TaskStatus | str, error: str | None, now: str
) -> None:
    value = status.value if isinstance(status, TaskStatus) else status
    finished = None if value == TaskStatus.RUNNING.value else now
    conn.execute(sa.update(tasks).where(tasks.c.id == task_id).values(
        status=value, last_error=error, finished_at=finished,
    ))


def list_recent(conn: sa.Connection, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute(
        sa.select(tasks).order_by(tasks.c.id.desc()).limit(limit)
    ).mappings()
    return [dict(r) for r in rows]
