"""程序化执行 Alembic 迁移，以及迁移前的自动备份。"""

import sqlite3
from datetime import datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_BACKUP_TS_FMT = "%Y%m%dT%H%M%SZ"


def _alembic_config(db_path: Path) -> Config:
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def current_revision(db_path: Path) -> str | None:
    """库当前所在的迁移版本；库文件不存在或尚未迁移过返回 None（不会创建文件）。"""
    if not db_path.exists():
        return None
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()


def backup_before_upgrade(db_path: Path, backups_dir: Path, now: datetime) -> Path | None:
    """库已存在且落后于 head 时，先整库备份一份再迁移；新库或已在 head 返回 None。"""
    current = current_revision(db_path)
    if current is None:
        return None
    if current == ScriptDirectory.from_config(_alembic_config(db_path)).get_current_head():
        return None
    backups_dir.mkdir(parents=True, exist_ok=True)
    out = backups_dir / f"pre-upgrade-{current}-{now.strftime(_BACKUP_TS_FMT)}.db"
    src, dst = sqlite3.connect(db_path), sqlite3.connect(out)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return out


def upgrade_to_head(db_path: Path) -> None:
    command.upgrade(_alembic_config(db_path), "head")
