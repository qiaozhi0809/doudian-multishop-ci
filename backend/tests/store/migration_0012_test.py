"""迁移 0012：shop.im_enabled 开关与 im_message 表。"""

import sqlalchemy as sa
from alembic import command

from app.store import shop_store
from app.store.db import make_engine
from app.store.migrate import _alembic_config, current_revision, upgrade_to_head
from tests.store.migration_0008_test import _raw_insert_shop
from tests.store.migration_test import _tables, _upgrade_to


def test_upgrade_adds_im_columns_and_table(tmp_path):
    db = tmp_path / "app.db"
    upgrade_to_head(db)
    eng = make_engine(db)
    with eng.begin() as conn:
        sid = shop_store.create(conn, "测试店", "2026-11-26T00:00:00Z")
        assert shop_store.get(conn, sid)["im_enabled"] == 0
        insp = sa.inspect(conn)
        assert "im_message" in insp.get_table_names()
        indexes = {i["name"]: i for i in insp.get_indexes("im_message")}
        unique = indexes["uq_im_message_shop_msg"]
        assert unique["unique"] and unique["column_names"] == ["shop_id", "message_id"]
        assert indexes["idx_im_message_conv"]["column_names"] == [
            "shop_id", "conversation_id", "sent_at",
        ]
        assert indexes["idx_im_message_captured"]["column_names"] == ["captured_at"]
        assert [fk["referred_table"] for fk in insp.get_foreign_keys("im_message")] == ["shop"]
    eng.dispose()


def test_existing_shops_default_off(tmp_path):
    db = tmp_path / "app.db"
    _upgrade_to(db, "0011")
    _raw_insert_shop(db, name="测试店")
    upgrade_to_head(db)
    eng = make_engine(db)
    with eng.connect() as conn:
        assert shop_store.get(conn, 1)["im_enabled"] == 0
    eng.dispose()


def test_downgrade_drops_im_message(tmp_path):
    db = tmp_path / "app.db"
    _upgrade_to(db, "0011")
    _raw_insert_shop(db, name="测试店")
    upgrade_to_head(db)
    command.downgrade(_alembic_config(db), "0011")
    assert current_revision(db) == "0011"
    assert "im_message" not in _tables(db)
    eng = make_engine(db)
    with eng.connect() as conn:
        assert "im_enabled" not in {c["name"] for c in sa.inspect(conn).get_columns("shop")}
        assert conn.exec_driver_sql("SELECT name FROM shop").scalar() == "测试店"
    eng.dispose()
