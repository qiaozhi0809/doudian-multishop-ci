"""backup_run 读写（ENG-06）。"""

import sqlalchemy as sa

from app.store.backup_schema import backup_run


def insert(
    conn: sa.Connection, *, file_name: str, size_bytes: int, trigger: str,
    actor: str | None, now: str,
) -> None:
    conn.execute(sa.insert(backup_run).values(
        file_name=file_name, size_bytes=size_bytes, trigger=trigger,
        actor=actor, created_at=now,
    ))


def list_recent(conn: sa.Connection, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        sa.select(backup_run).order_by(backup_run.c.created_at.desc(), backup_run.c.id.desc())
        .limit(limit)
    ).mappings()
    return [dict(r) for r in rows]


def delete(conn: sa.Connection, file_name: str) -> None:
    conn.execute(sa.delete(backup_run).where(backup_run.c.file_name == file_name))
