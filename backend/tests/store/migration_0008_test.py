"""迁移 0008：shop 的代理三列搬进 proxy_pool（proxy-pool 1.4）。"""

import sqlite3

import sqlalchemy as sa

from app.shared.secret_box import DevKeyBox
from app.store import proxy_pool_store, shop_store
from app.store.db import make_engine
from app.store.migrate import upgrade_to_head
from tests.store.migration_test import _upgrade_to

_TS = "2026-11-25T00:00:00Z"


def _raw_insert_shop(db, *, name, **cols) -> None:
    values = {"name": name, "created_at": _TS, "updated_at": _TS, **cols}
    conn = sqlite3.connect(db)
    try:
        keys = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        conn.execute(f"INSERT INTO shop ({keys}) VALUES ({marks})", list(values.values()))
        conn.commit()
    finally:
        conn.close()


def test_0008_moves_shop_proxy_into_pool(tmp_path):
    db = tmp_path / "app.db"
    _upgrade_to(db, "0007")
    _raw_insert_shop(db, name="店A", egress_mode="proxy", proxy_url=b"CIPHER",
                     proxy_display="203.0.113.5:8000", proxy_expires_at="2026-12-31")
    upgrade_to_head(db)
    eng = make_engine(db)
    with eng.connect() as conn:
        shop = shop_store.get(conn, 1)
        assert shop["proxy_url"] == b"CIPHER" and shop["proxy_expires_at"] == "2026-12-31"
        assert shop["proxy_display"] == "203.0.113.5:8000"
        assert proxy_pool_store.get(conn, shop["proxy_pool_id"])["identity"] == "legacy:1"
        assert "proxy_url" not in {c["name"] for c in sa.inspect(conn).get_columns("shop")}
    eng.dispose()


def test_0008_one_pool_item_per_proxy_shop_and_direct_untouched(tmp_path):
    db = tmp_path / "app.db"
    _upgrade_to(db, "0007")
    _raw_insert_shop(db, name="直连店", egress_mode="direct")
    _raw_insert_shop(db, name="店B", egress_mode="proxy", proxy_url=b"C2",
                     proxy_display="203.0.113.6:8000")
    _raw_insert_shop(db, name="店C", egress_mode="proxy", proxy_url=b"C2",  # 同一代理也各建一项
                     proxy_display="203.0.113.6:8000", status="disabled")
    upgrade_to_head(db)
    eng = make_engine(db)
    with eng.connect() as conn:
        direct, b, c = shop_store.list(conn)
        assert direct["proxy_pool_id"] is None and direct["proxy_url"] is None
        assert b["proxy_pool_id"] != c["proxy_pool_id"]
        assert b["proxy_expires_at"] is None
        legacy = {r["identity"] for r in proxy_pool_store.list_legacy(conn)}
        assert legacy == {"legacy:2", "legacy:3"}
        assert "uq_shop_pool" in {i["name"] for i in sa.inspect(conn).get_indexes("shop")}
    eng.dispose()


def test_0008_keeps_ciphertext_decryptable(tmp_path):
    db = tmp_path / "app.db"
    box = DevKeyBox(tmp_path / "k")
    url = "http://user-x:pw-y@203.0.113.5:8000"
    _upgrade_to(db, "0007")
    _raw_insert_shop(db, name="店A", egress_mode="proxy", proxy_url=box.encrypt(url.encode()),
                     proxy_display="203.0.113.5:8000")
    upgrade_to_head(db)
    eng = make_engine(db)
    with eng.connect() as conn:
        assert box.decrypt(shop_store.get(conn, 1)["proxy_url"]).decode() == url
    eng.dispose()


def test_0008_on_empty_db(tmp_path):
    db = tmp_path / "app.db"
    _upgrade_to(db, "0007")
    upgrade_to_head(db)
    eng = make_engine(db)
    with eng.connect() as conn:
        assert proxy_pool_store.list_with_usage(conn) == []
    eng.dispose()
