"""session 表：每店只保留最新一条（cookie / token 均为密文）。"""

from dataclasses import dataclass

import sqlalchemy as sa

from app.store.schema import session


@dataclass(frozen=True)
class SessionRow:
    shop_id: int
    cookies_blob: bytes
    token_blob: bytes
    device_json: str
    expires_at: str | None


def save(conn: sa.Connection, row: SessionRow, now: str) -> None:
    conn.execute(sa.delete(session).where(session.c.shop_id == row.shop_id))
    conn.execute(sa.insert(session).values(
        shop_id=row.shop_id, cookies=row.cookies_blob, token=row.token_blob,
        device_params=row.device_json, expires_at=row.expires_at, updated_at=now,
    ))


def load(conn: sa.Connection, shop_id: int) -> SessionRow | None:
    r = conn.execute(
        sa.select(session).where(session.c.shop_id == shop_id)
        .order_by(session.c.updated_at.desc(), session.c.id.desc()).limit(1)
    ).mappings().first()
    if r is None:
        return None
    return SessionRow(shop_id, r["cookies"], r["token"], r["device_params"], r["expires_at"])
