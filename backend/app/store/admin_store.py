"""admin_user / admin_session 读写。会话只存令牌的 SHA-256。"""

from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa

from app.store.schema import admin_session, admin_user


def count_users(conn: sa.Connection) -> int:
    return int(conn.execute(sa.select(sa.func.count()).select_from(admin_user)).scalar_one())


def create_user(conn: sa.Connection, username: str, password_hash: str, now: str) -> int:
    res = conn.execute(sa.insert(admin_user).values(
        username=username, password_hash=password_hash, password_changed_at=now, created_at=now,
    ))
    return int(res.inserted_primary_key[0])


def get_user_by_name(conn: sa.Connection, username: str) -> Mapping[str, Any] | None:
    row = conn.execute(
        sa.select(admin_user).where(admin_user.c.username == username)
    ).mappings().first()
    return dict(row) if row else None


def get_user(conn: sa.Connection, user_id: int) -> Mapping[str, Any] | None:
    row = conn.execute(
        sa.select(admin_user).where(admin_user.c.id == user_id)
    ).mappings().first()
    return dict(row) if row else None


def set_failures(
    conn: sa.Connection, user_id: int, failed_attempts: int, locked_until: str | None
) -> None:
    conn.execute(sa.update(admin_user).where(admin_user.c.id == user_id).values(
        failed_attempts=failed_attempts, locked_until=locked_until))


def set_password(conn: sa.Connection, user_id: int, password_hash: str, now: str) -> None:
    conn.execute(sa.update(admin_user).where(admin_user.c.id == user_id).values(
        password_hash=password_hash, password_changed_at=now,
        failed_attempts=0, locked_until=None))


def create_session(
    conn: sa.Connection, token_hash: str, user_id: int, now: str, expires_at: str
) -> None:
    conn.execute(sa.insert(admin_session).values(
        token_hash=token_hash, user_id=user_id, created_at=now, last_seen_at=now,
        expires_at=expires_at))


def get_session(conn: sa.Connection, token_hash: str) -> Mapping[str, Any] | None:
    row = conn.execute(
        sa.select(admin_session).where(admin_session.c.token_hash == token_hash)
    ).mappings().first()
    return dict(row) if row else None


def touch_session(conn: sa.Connection, token_hash: str, now: str) -> None:
    conn.execute(sa.update(admin_session).where(admin_session.c.token_hash == token_hash)
                 .values(last_seen_at=now))


def delete_session(conn: sa.Connection, token_hash: str) -> None:
    conn.execute(sa.delete(admin_session).where(admin_session.c.token_hash == token_hash))


def delete_user_sessions(
    conn: sa.Connection, user_id: int, except_token_hash: str | None = None
) -> None:
    stmt = sa.delete(admin_session).where(admin_session.c.user_id == user_id)
    if except_token_hash is not None:
        stmt = stmt.where(admin_session.c.token_hash != except_token_hash)
    conn.execute(stmt)
