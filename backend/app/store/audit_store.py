"""audit_log 写入。摘要入库前再过一遍脱敏。"""

import json

import sqlalchemy as sa

from app.domain.audit import CallRecord
from app.shared.redact import redact_mapping
from app.store.schema import audit_log


def _dump(d: dict) -> str:
    return json.dumps(redact_mapping(d), ensure_ascii=False)


def insert(conn: sa.Connection, record: CallRecord, now: str) -> None:
    conn.execute(sa.insert(audit_log).values(
        shop_id=record.shop_id, actor=record.actor, action=record.action,
        req_summary=_dump(record.req_summary), resp_summary=_dump(record.resp_summary),
        result=record.result, duration_ms=record.duration_ms, created_at=now,
    ))
