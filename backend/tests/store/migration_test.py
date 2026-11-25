import sqlalchemy as sa

from app.store import aggregate_schema, schema  # noqa: F401  M5 表注册到同一 metadata
from app.store.db import make_engine
from app.store.migrate import upgrade_to_head

TABLES = {
    "shop", "session", "orders", "order_items", "shop_address",
    "ebill_account", "waybill_template", "courier", "audit_log",
    "waybills", "tasks", "print_job",
    "aftersale", "product_snapshot", "stock_snapshot", "fund_unsettled", "margin_account",
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
