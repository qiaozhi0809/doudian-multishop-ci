"""SQLite 引擎。每个连接开启 WAL 与外键。"""

from pathlib import Path

from sqlalchemy import Engine, create_engine, event

DB_FILE_NAME = "app.db"


def make_engine(db_path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine
