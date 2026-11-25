"""ENG-06：SQLite 快照（WAL 安全）与保留策略。"""

import sqlite3
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa

from app.service.backup import BackupService

MARKER = "INSERT INTO audit_log (shop_id, actor, action, req_summary, resp_summary, result, " \
         "duration_ms, created_at) VALUES (NULL, 'admin', 'backup_marker', '{}', '{}', 'ok', 0, " \
         "'2026-11-25T00:00:00Z')"


class DayClock:
    """每调用一次前进一天：模拟每日快照。"""

    def __init__(self) -> None:
        self.now = datetime(2026, 11, 25, 4, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(days=1)
        return self.now


def _count_markers(db_path) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(
            "SELECT count(*) FROM audit_log WHERE action = 'backup_marker'").fetchone()[0]
    finally:
        conn.close()


def test_snapshot_contains_committed_wal_rows(engine, tmp_path, clock):
    """WAL 模式下已提交事务必须在快照里（直接复制 app.db 会丢）。"""
    service = BackupService(engine, tmp_path / "backups", keep=7, clock=clock)
    with engine.begin() as conn:
        conn.execute(sa.text(MARKER))

    created = service.create(actor="admin", trigger="manual")

    target = tmp_path / "backups" / created["file_name"]
    assert target.is_file()
    assert created["size_bytes"] == target.stat().st_size > 0
    assert _count_markers(target) == 1


def test_keep_latest_n(engine, tmp_path):
    service = BackupService(engine, tmp_path / "backups", keep=2, clock=DayClock())
    names = [service.create(trigger="daily")["file_name"] for _ in range(4)]

    remaining = [p.name for p in (tmp_path / "backups").glob("app-*.db")]
    assert sorted(remaining) == sorted(names[-2:])
    listed = [row["file_name"] for row in service.snapshots()]
    assert listed == [names[3], names[2]]  # 最新的在前
    assert all(row["exists"] for row in service.snapshots())


def test_same_second_backups_do_not_overwrite(engine, tmp_path, clock):
    """同一秒内连续触发：追加序号，不覆盖已有快照。"""
    service = BackupService(engine, tmp_path / "backups", keep=7, clock=clock)
    first = service.create(trigger="manual")["file_name"]
    second = service.create(trigger="manual")["file_name"]

    assert first != second
    assert (tmp_path / "backups" / first).is_file()
    assert (tmp_path / "backups" / second).is_file()


def test_snapshot_is_restorable(engine, tmp_path, clock):
    """恢复演练：快照可作为独立 SQLite 库打开并查询。"""
    service = BackupService(engine, tmp_path / "backups", keep=7, clock=clock)
    with engine.begin() as conn:
        conn.execute(sa.text(MARKER))
    name = service.create(trigger="manual")["file_name"]

    copy = tmp_path / "restored.db"
    copy.write_bytes((tmp_path / "backups" / name).read_bytes())
    assert _count_markers(copy) == 1
