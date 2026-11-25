"""ENG-06：SQLite 每日快照与保留策略。

WAL 模式下直接复制 app.db 会丢已提交事务，必须走 SQLite 在线备份 API
（sqlite3 Connection.backup，等价于命令行 `.backup` / `VACUUM INTO`）。
恢复只能在服务停止后手工替换 app.db，步骤见 docs/design/deployment.md。
"""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import structlog
from sqlalchemy import Engine

from app.store import backup_store

log = structlog.get_logger()

SNAPSHOT_PREFIX = "app-"
SNAPSHOT_SUFFIX = ".db"
BACKUP_TIMEOUT_S = 30
ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> datetime:
    return datetime.now(UTC)


class BackupService:
    def __init__(
        self, engine: Engine, backups_dir: Path, *, keep: int = 7,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._engine = engine
        self._dir = backups_dir
        self._keep = keep
        self._clock = clock

    def create(self, actor: str | None = None, trigger: str = "manual") -> dict:
        """生成一份快照并清理超期文件；返回快照信息与本次删除的文件名。"""
        self._dir.mkdir(parents=True, exist_ok=True)
        now = self._clock()
        target = self._target_path(now)
        db_path = self._engine.url.database
        if not db_path:
            raise RuntimeError("引擎没有可备份的数据库文件")
        self._copy(db_path, target)
        size = target.stat().st_size
        now_iso = now.strftime(ISO_FMT)
        with self._engine.begin() as conn:
            backup_store.insert(
                conn, file_name=target.name, size_bytes=size, trigger=trigger,
                actor=actor, now=now_iso,
            )
        pruned = self.prune()
        log.info("backup.created", file=target.name, size=size, trigger=trigger, pruned=len(pruned))
        return {
            "file_name": target.name, "size_bytes": size, "trigger": trigger,
            "actor": actor, "created_at": now_iso, "pruned": pruned,
        }

    def snapshots(self) -> list[dict]:
        with self._engine.connect() as conn:
            rows = backup_store.list_recent(conn)
        return [
            {**row, "exists": (self._dir / row["file_name"]).is_file()}
            for row in rows
        ]

    def prune(self) -> list[str]:
        """按文件名里的时间戳只保留最近 keep 份，删除同步清 backup_run 记录。"""
        files = sorted(
            self._dir.glob(f"{SNAPSHOT_PREFIX}*{SNAPSHOT_SUFFIX}"), key=_snapshot_key)
        excess = files[:-self._keep] if len(files) > self._keep else []
        removed: list[str] = []
        with self._engine.begin() as conn:
            for path in excess:
                path.unlink(missing_ok=True)
                backup_store.delete(conn, path.name)
                removed.append(path.name)
        return removed

    def _target_path(self, now: datetime) -> Path:
        stamp = now.strftime("%Y%m%d-%H%M%S")
        target = self._dir / f"{SNAPSHOT_PREFIX}{stamp}{SNAPSHOT_SUFFIX}"
        index = 1
        while target.exists():  # 同一秒内重复触发：追加序号，不覆盖已有快照
            target = self._dir / f"{SNAPSHOT_PREFIX}{stamp}-{index}{SNAPSHOT_SUFFIX}"
            index += 1
        return target

    @staticmethod
    def _copy(db_path: str, target: Path) -> None:
        source = sqlite3.connect(db_path, timeout=BACKUP_TIMEOUT_S)
        try:
            dest = sqlite3.connect(str(target), timeout=BACKUP_TIMEOUT_S)
            try:
                source.backup(dest)
            finally:
                dest.close()
        finally:
            source.close()
        # 快照独立成库：切回 WAL 由使用方决定；这里保持默认 DELETE 模式即可


_STAMP_LEN = len("YYYYMMDD-HHMMSS")  # 15


def _snapshot_key(path: Path) -> tuple[str, int]:
    """按 (日期时间戳, 同秒序号) 排序。纯字符串排序会把 `-1.db` 排到 `.db` 前面。"""
    core = path.name[len(SNAPSHOT_PREFIX):-len(SNAPSHOT_SUFFIX)]
    stamp, _, suffix = core[: _STAMP_LEN], core[_STAMP_LEN:], ""
    if suffix.startswith("-"):
        suffix = suffix[1:]
    return stamp, int(suffix or 0)
