"""print_job 读写（data-model 6.2 ⑤-b）。每次打印尝试一条；状态推进在 service。"""

import sqlalchemy as sa

from app.domain.print_status import PrintJobStatus
from app.store.schema import print_job, waybills


def insert(conn: sa.Connection, *, waybill_id: int, printer_name: str, now: str) -> int:
    return int(conn.execute(sa.insert(print_job).values(
        waybill_id=waybill_id, printer_name=printer_name,
        status=PrintJobStatus.QUEUED.value, attempts=0, created_at=now,
    )).inserted_primary_key[0])


def bump_attempts(conn: sa.Connection, job_id: int, attempts: int) -> None:
    conn.execute(
        sa.update(print_job).where(print_job.c.id == job_id).values(attempts=attempts))


def finish(
    conn: sa.Connection, job_id: int, status: PrintJobStatus,
    result_code: str | None, result_detail: str | None, now: str,
) -> None:
    conn.execute(
        sa.update(print_job).where(print_job.c.id == job_id).values(
            status=status.value, result_code=result_code,
            result_detail=result_detail, finished_at=now,
        )
    )


def get(conn: sa.Connection, job_id: int) -> dict | None:
    row = conn.execute(
        sa.select(print_job).where(print_job.c.id == job_id)
    ).mappings().first()
    return dict(row) if row else None


def by_ids(conn: sa.Connection, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    rows = conn.execute(
        sa.select(print_job).where(print_job.c.id.in_(ids)).order_by(print_job.c.id)
    ).mappings()
    return [dict(r) for r in rows]


def ids_by_waybills(conn: sa.Connection, waybill_ids: list[int]) -> list[int]:
    if not waybill_ids:
        return []
    return list(conn.execute(
        sa.select(print_job.c.id)
        .where(print_job.c.waybill_id.in_(waybill_ids))
        .order_by(print_job.c.id)
    ).scalars())


def latest_by_waybills(
    conn: sa.Connection, waybill_ids: list[int]
) -> dict[int, dict]:
    """每张面单最近一次打印任务（按 id 倒序取第一条）。"""
    if not waybill_ids:
        return {}
    rows = conn.execute(
        sa.select(print_job)
        .where(print_job.c.waybill_id.in_(waybill_ids))
        .order_by(print_job.c.waybill_id, print_job.c.id.desc())
    ).mappings()
    out: dict[int, dict] = {}
    for row in rows:
        out.setdefault(row["waybill_id"], dict(row))
    return out


def with_waybill_no(
    conn: sa.Connection, waybill_ids: list[int]
) -> dict[int, dict]:
    """面单的可打印信息（waybill_no / status / 是否有 print_data）。"""
    if not waybill_ids:
        return {}
    rows = conn.execute(
        sa.select(
            waybills.c.id, waybills.c.waybill_no, waybills.c.status,
            waybills.c.print_data,
        ).where(waybills.c.id.in_(waybill_ids))
    ).mappings()
    return {row["id"]: dict(row) for row in rows}
