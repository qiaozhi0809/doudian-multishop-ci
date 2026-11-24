"""Alembic 环境：只做在线迁移，连接经 make_engine（带 WAL 与外键）。"""

from pathlib import Path

from alembic import context

from app.store.db import make_engine

config = context.config
db_path = Path(config.get_main_option("sqlalchemy.url").removeprefix("sqlite:///"))

engine = make_engine(db_path)
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
