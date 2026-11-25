"""两步提交第①步：取号 / 一体 / 作废的预览（不发任何写请求）。"""

from datetime import timedelta

import pytest
import sqlalchemy as sa

from app.domain.errors import InvalidRequest, NotFound
from app.service.label_preview import LabelPreviewService
from app.store.schema import (
    ebill_account,
    order_items,
    orders,
    shop,
    shop_address,
    waybill_template,
    waybills,
)

NOW = "2026-11-25T00:00:00Z"


def add_shop(engine, name="店A", status="active") -> int:
    with engine.begin() as conn:
        return int(conn.execute(sa.insert(shop).values(
            name=name, status=status, created_at=NOW, updated_at=NOW,
        )).inserted_primary_key[0])


def add_address(engine, shop_id, address_id="a1", is_default=1) -> None:
    with engine.begin() as conn:
        conn.execute(sa.insert(shop_address).values(
            shop_id=shop_id, address_id=address_id, name="发货人", phone="138****0000",
            region="内蒙古自治区通辽市", detail="<详细地址>", province_id=15,
            province_name="内蒙古自治区", city_id=150500, city_name="通辽市",
            town_id=150522, town_name="科尔沁左翼后旗", street_id=150522100,
            street_name="甘旗卡镇", is_default=is_default, synced_at=NOW,
        ))


def add_template(engine, shop_id, courier="zt", code="T-custom", is_custom=1) -> None:
    with engine.begin() as conn:
        conn.execute(sa.insert(waybill_template).values(
            shop_id=shop_id, template_code=code, courier_code=courier, name="模板",
            is_custom=is_custom, synced_at=NOW,
        ))


def add_account(engine, shop_id, courier="zt", balance=10, is_default=1) -> None:
    with engine.begin() as conn:
        conn.execute(sa.insert(ebill_account).values(
            shop_id=shop_id, courier_code=courier, ebill_id="e1", net_code="n1",
            balance=balance, is_default=is_default, synced_at=NOW,
        ))


def add_order(engine, shop_id, order_no="o1", *, status="pending_label",
              platform_status=2, combine_id: str | None = "c1", sku_id="s1") -> int:
    with engine.begin() as conn:
        order_id = int(conn.execute(sa.insert(orders).values(
            shop_id=shop_id, order_no=order_no, status=status,
            platform_status=platform_status, combine_id=combine_id, synced_at=NOW,
        )).inserted_primary_key[0])
        conn.execute(sa.insert(order_items).values(
            order_id=order_id, sku_order_id="so-" + order_no, sku_id=sku_id,
            product_id="p1", quantity=1,
        ))
    return order_id


def add_waybill(engine, shop_id, order_id, *, waybill_no="79200000000001", status="active") -> int:
    with engine.begin() as conn:
        return int(conn.execute(sa.insert(waybills).values(
            shop_id=shop_id, order_id=order_id, seq=1, courier_code="zt",
            waybill_no=waybill_no, status=status, obtained_at=NOW,
        )).inserted_primary_key[0])


class Env:
    def __init__(self, engine, clock):
        self.engine = engine
        self.service = LabelPreviewService(engine, dry_run=False, clock=clock)
        self.clock = clock

    def ready_shop(self, name="店A") -> int:
        shop_id = add_shop(self.engine, name)
        add_address(self.engine, shop_id)
        add_template(self.engine, shop_id)
        add_account(self.engine, shop_id)
        return shop_id


def test_preview_groups_by_shop_and_blocks_missing_fields(engine, clock):
    env = Env(engine, clock)
    shop1 = env.ready_shop("店A")
    shop2 = env.ready_shop("店B")
    ok1 = add_order(engine, shop1, "o1")
    bad = add_order(engine, shop1, "o2", combine_id=None)
    ok2 = add_order(engine, shop2, "o3")

    record = env.service.preview_obtain([ok1, bad, ok2], {}, actor="admin")
    view = env.service.view(record)

    assert {s["shop_id"] for s in view["shops"]} == {shop1, shop2}
    by_shop = {s["shop_id"]: s for s in view["shops"]}
    assert by_shop[shop1]["ready_order_ids"] == [ok1]
    assert by_shop[shop1]["courier_code"] == "zt"
    assert by_shop[shop1]["template_code"] == "T-custom"
    assert by_shop[shop1]["ebill_id"] == "e1"
    assert view["blocked"][0]["order_id"] == bad
    assert "combine_id" in view["blocked"][0]["reason"]
    assert view["total_ready"] == 2 and view["total_blocked"] == 1


def test_preview_marks_synced_orders_pending_label(engine, clock):
    env = Env(engine, clock)
    shop_id = env.ready_shop()
    order_id = add_order(engine, shop_id, "o1", status="synced")

    env.service.preview_obtain([order_id], {}, actor="admin")
    with engine.connect() as conn:
        assert conn.execute(sa.select(orders.c.status).where(
            orders.c.id == order_id)).scalar_one() == "pending_label"


def test_preview_shop_error_when_no_default_address(engine, clock):
    env = Env(engine, clock)
    good = env.ready_shop("店A")
    bad_shop = add_shop(engine, "店B")  # 无地址 / 模板 / 账户
    o1 = add_order(engine, good, "o1")
    o2 = add_order(engine, bad_shop, "o2")

    view = env.service.view(env.service.preview_obtain([o1, o2], {}, actor="admin"))
    assert [s["shop_id"] for s in view["shops"]] == [good]
    assert view["shop_errors"][0]["shop_id"] == bad_shop
    assert "地址" in view["shop_errors"][0]["reason"]


def test_preview_rejects_courier_without_template_or_account(engine, clock):
    env = Env(engine, clock)
    shop_id = env.ready_shop()
    o1 = add_order(engine, shop_id, "o1")

    view = env.service.view(
        env.service.preview_obtain([o1], {"1": "yunda"}, actor="admin"))
    assert view["shops"] == []
    assert view["shop_errors"][0]["shop_id"] == shop_id
    assert "yunda" in view["shop_errors"][0]["reason"]


def test_preview_blocks_orders_with_active_waybill(engine, clock):
    env = Env(engine, clock)
    shop_id = env.ready_shop()
    order_id = add_order(engine, shop_id, "o1", status="label_obtained")
    add_waybill(engine, shop_id, order_id)

    view = env.service.view(env.service.preview_obtain([order_id], {}, actor="admin"))
    assert view["total_ready"] == 0
    assert "面单" in view["blocked"][0]["reason"]


def test_preview_missing_order_not_found(engine, clock):
    env = Env(engine, clock)
    with pytest.raises(NotFound):
        env.service.preview_obtain([9999], {}, actor="admin")


def test_preview_is_single_use_and_expires(engine, clock):
    env = Env(engine, clock)
    shop_id = env.ready_shop()
    o1 = add_order(engine, shop_id, "o1")
    record = env.service.preview_obtain([o1], {}, actor="admin")

    taken = env.service.previews.take(record.preview_id, "admin")
    assert taken.preview_id == record.preview_id
    with pytest.raises(InvalidRequest):
        env.service.previews.take(record.preview_id, "admin")

    record2 = env.service.preview_obtain([o1], {}, actor="admin")
    clock.now = clock.now + timedelta(minutes=11)
    with pytest.raises(InvalidRequest):
        env.service.previews.take(record2.preview_id, "admin")


def test_preview_belongs_to_actor(engine, clock):
    env = Env(engine, clock)
    shop_id = env.ready_shop()
    o1 = add_order(engine, shop_id, "o1")
    record = env.service.preview_obtain([o1], {}, actor="admin")
    with pytest.raises(InvalidRequest):
        env.service.previews.take(record.preview_id, "other")


def test_void_preview_lists_active_waybills_and_blocks_shipped(engine, clock):
    env = Env(engine, clock)
    shop_id = env.ready_shop()
    labeled = add_order(engine, shop_id, "o1", status="label_obtained")
    shipped = add_order(engine, shop_id, "o2", status="shipped", platform_status=3)
    wid = add_waybill(engine, shop_id, labeled)
    add_waybill(engine, shop_id, shipped, waybill_no="79200000000002")

    view = env.service.view(env.service.preview_void([labeled, shipped], actor="admin"))
    assert view["mode"] == "void"
    assert view["shops"][0]["waybills"][0]["waybill_id"] == wid
    assert view["blocked"][0]["order_id"] == shipped
