import sqlite3
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import command

from app.store import (  # noqa: F401  M4 / M5 / M7 与飞鸽表注册到同一 metadata
    aggregate_schema,
    backup_schema,
    im_schema,
    notification_schema,
    reconcile_schema,
    schema,
    shipping_schema,
)
from app.store.db import make_engine
from app.store.migrate import (
    _alembic_config,
    backup_before_upgrade,
    current_revision,
    upgrade_to_head,
)

TABLES = {
    "shop", "session", "orders", "order_items", "shop_address",
    "ebill_account", "waybill_template", "courier", "audit_log",
    "waybills", "tasks", "print_job",
    "aftersale", "product_snapshot", "stock_snapshot", "fund_unsettled", "margin_account",
    "order_fact", "reconcile_run", "reconcile_findings", "shipment",
    "backup_run", "proxy_pool", "notification", "sync_baseline", "im_message",
}


def test_migration_creates_tables(tmp_path):
    db = tmp_path / "app.db"
    upgrade_to_head(db)
    eng = make_engine(db)
    with eng.connect() as conn:
        names = set(sa.inspect(conn).get_table_names())
        assert TABLES <= names
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    eng.dispose()


def test_upgrade_is_idempotent(tmp_path):
    db = tmp_path / "app.db"
    upgrade_to_head(db)
    upgrade_to_head(db)


def test_schema_py_matches_migration(engine):
    insp = sa.inspect(engine)
    for table in schema.metadata.sorted_tables:
        db_cols = {c["name"]: c for c in insp.get_columns(table.name)}
        assert set(db_cols) == {c.name for c in table.columns}, table.name
        for col in table.columns:
            assert db_cols[col.name]["nullable"] == (col.nullable and not col.primary_key), (
                table.name, col.name,
            )
        model_idx = {i.name for i in table.indexes}
        db_idx = {i["name"] for i in insp.get_indexes(table.name)}
        assert model_idx <= db_idx, (table.name, model_idx - db_idx)


NOW = datetime(2026, 12, 1, tzinfo=UTC)


def _upgrade_to(db, rev):
    command.upgrade(_alembic_config(db), rev)


def _tables(db):
    conn = sqlite3.connect(db)
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def test_backup_skipped_for_new_db(tmp_path):
    assert backup_before_upgrade(tmp_path / "app.db", tmp_path / "bk", NOW) is None
    assert not (tmp_path / "app.db").exists()


def test_backup_skipped_when_at_head(tmp_path):
    db = tmp_path / "app.db"
    upgrade_to_head(db)
    assert backup_before_upgrade(db, tmp_path / "bk", NOW) is None


def test_backup_copies_db_when_behind_head(tmp_path):
    db = tmp_path / "app.db"
    _upgrade_to(db, "0006")  # 落后于 head 才需要备份
    assert current_revision(db) == "0006"
    out = backup_before_upgrade(db, tmp_path / "bk", NOW)
    assert out.name == "pre-upgrade-0006-20261201T000000Z.db"
    assert "shipment" in _tables(out)
    assert "backup_run" not in _tables(out)  # 备份的是迁移前的库
