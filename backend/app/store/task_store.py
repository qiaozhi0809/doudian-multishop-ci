"""tasks 读写与幂等键复用（backend 5.11）：success 不重跑，failed 复用行 attempts+1。

另含 M7 的掉线 / 重启恢复：
- `recover_after_restart`：进程重启时把 running 的写任务转 verifying（结果不明，走 5.12），
  其余 running 转 queued（backend 5.7）。
- `verify_running_for_shop`：某店会话失效时，把该店 running 的写任务转 verifying，
  避免「任务永远占着幂等键」导致重登后无法重试。
"""

import json
from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa

from app.domain.task_status import TaskStatus, TaskType
from app.store.schema import tasks

# 会向平台发出写请求、崩溃 / 掉线时结果无法确定的类型
UNKNOWN_RESULT_TYPES = (
    TaskType.OBTAIN_LABEL.value,
    TaskType.FETCH_AND_SHIP.value,
    TaskType.VOID_LABEL.value,
    TaskType.SHIP.value,
)
RESTART_REASON = "进程重启时任务未完成，结果待核实"
SESSION_REASON = "会话失效时任务未完成，请重新登录后确认再重试"


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


def recover_after_restart(conn: sa.Connection, now: str) -> dict[str, int]:
    """进程重启恢复：写任务 running → verifying；其余 running → queued。返回各类条数。"""
    verifying = conn.execute(
        sa.update(tasks).where(
            tasks.c.status == TaskStatus.RUNNING.value,
            tasks.c.type.in_(UNKNOWN_RESULT_TYPES),
        ).values(
            status=TaskStatus.VERIFYING.value, last_error=RESTART_REASON, finished_at=now,
        )
    ).rowcount
    queued = conn.execute(
        sa.update(tasks).where(tasks.c.status == TaskStatus.RUNNING.value).values(
            status=TaskStatus.QUEUED.value, started_at=None,
        )
    ).rowcount
    return {"verifying": verifying, "queued": queued}


def verify_running_for_shop(conn: sa.Connection, shop_id: int, now: str) -> int:
    """会话失效：该店 running 的写任务结果不明 → verifying（重登后可重新提交）。"""
    return conn.execute(
        sa.update(tasks).where(
            tasks.c.shop_id == shop_id,
            tasks.c.status == TaskStatus.RUNNING.value,
            tasks.c.type.in_(UNKNOWN_RESULT_TYPES),
        ).values(
            status=TaskStatus.VERIFYING.value, last_error=SESSION_REASON, finished_at=now,
        )
    ).rowcount
