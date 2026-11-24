import sqlalchemy as sa

from app.domain.models import AddressDTO, CourierDTO, EbillAccountDTO, TemplateDTO
from app.store import base_data_store, shop_store
from tests.store.conftest import LATER, NOW


def _addr(address_id, default=False, name="发货人"):
    return AddressDTO(address_id, name, "138****0000", "省市区", "x路", 1, "省", 2, "市", 3, "区",
                      4, "街", default, {"a": 1})


def _count(conn, table):
    return conn.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar()


def test_replace_addresses_by_unique_key(engine):
    with engine.begin() as conn:
        sid = shop_store.create(conn, "A", NOW)
        base_data_store.replace_addresses(conn, sid, [_addr("1", True), _addr("2")], NOW)
        base_data_store.replace_addresses(conn, sid, [_addr("2", True, "新名"), _addr("3")], LATER)
        rows = conn.execute(
            sa.text("SELECT address_id, name, is_default, synced_at FROM shop_address ORDER BY 1")
        ).all()
        assert [(r.address_id, r.name, r.is_default) for r in rows] == [
            ("2", "新名", 1), ("3", "发货人", 0)]
        assert {r.synced_at for r in rows} == {LATER}


def test_replace_is_per_shop(engine):
    with engine.begin() as conn:
        a, b = shop_store.create(conn, "A", NOW), shop_store.create(conn, "B", NOW)
        base_data_store.replace_couriers(conn, a, [CourierDTO("sf", "顺丰", True, {})], NOW)
        base_data_store.replace_couriers(conn, b, [CourierDTO("sf", "顺丰", True, {})], NOW)
        base_data_store.replace_couriers(conn, a, [], LATER)
        assert _count(conn, "courier") == 1


def test_replace_templates_accounts(engine):
    with engine.begin() as conn:
        sid = shop_store.create(conn, "A", NOW)
        base_data_store.replace_templates(
            conn, sid,
            [TemplateDTO("t1", "sf", "模板", True, {"x": 1}),
             TemplateDTO("t2", "sf", "官方", False, {})],
            NOW)
        base_data_store.replace_ebill_accounts(
            conn, sid,
            [EbillAccountDTO("sf", "10", "n1", "网点", 1, 5, True, {}),
             EbillAccountDTO("sf", "10", "n2", "网点2", 1, 0, False, {})], NOW)
        flags = conn.execute(
            sa.text("SELECT template_code, is_custom FROM waybill_template ORDER BY 1")
        ).all()
        assert [tuple(r) for r in flags] == [("t1", 1), ("t2", 0)]
        assert _count(conn, "ebill_account") == 2
        base_data_store.replace_ebill_accounts(
            conn, sid, [EbillAccountDTO("sf", "10", "n1", "网点", 1, 9, True, {})], LATER)
        assert conn.execute(sa.text("SELECT balance FROM ebill_account")).scalars().all() == [9]
