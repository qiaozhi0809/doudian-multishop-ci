"""手工维护的店铺ID / 收款信息：格式校验、添加店铺时写店铺ID、修改留审计（只记字段名）。"""

import json
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa

from app.domain.errors import InvalidRequest
from app.service.egress import EgressService
from app.service.events import EventBus
from app.service.shop_admin import ShopAdminService
from app.shared.secret_box import DevKeyBox
from app.store import shop_profile_store, shop_store

NOW = datetime(2026, 12, 1, tzinfo=UTC)


@pytest.fixture
def admin(engine, tmp_path):
    events = EventBus()
    events.publish = lambda topic, data: None  # type: ignore[method-assign]
    egress = EgressService(engine, DevKeyBox(tmp_path / "k"), events, None,  # type: ignore[arg-type]
                           clock=lambda: NOW)
    return ShopAdminService(engine, events, egress, clock=lambda: NOW)


def _profile(engine, sid):
    with engine.connect() as conn:
        return shop_profile_store.get(conn, sid) or {}


def _audits(engine, action):
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(
            sa.text("select * from audit_log where action = :a"), {"a": action}).mappings()]


@pytest.mark.parametrize(("field", "value"), [
    ("bank_tail", "123"),
    ("bank_tail", "12345"),
    ("bank_tail", "62220000000000001234"),  # 粘贴了整串卡号
    ("bank_tail", "12a4"),
    ("platform_shop_id", "abc"),
    ("platform_shop_id", "1" * 21),
    ("bank_name", "示" * 51),
    ("bank_tail", "１２３４"),  # 全角数字
    ("platform_shop_id", "١٢٣"),  # 其他 Unicode 数字
])
def test_update_rejects_bad_profile_values(engine, admin, field, value):
    sid = admin.create("店A")
    with pytest.raises(InvalidRequest):
        admin.update(sid, **{field: value})
    assert _profile(engine, sid).get(field) is None


def test_update_accepts_valid_values_and_blank_clears(engine, admin):
    sid = admin.create("店A")
    admin.update(sid, platform_shop_id=" 100000001 ", bank_name="示例银行", bank_tail="0000")
    p = _profile(engine, sid)
    assert (p["platform_shop_id"], p["bank_name"], p["bank_tail"]) == (
        "100000001", "示例银行", "0000")
    admin.update(sid, platform_shop_id="", bank_name="", bank_tail="")
    p = _profile(engine, sid)
    assert (p["platform_shop_id"], p["bank_name"], p["bank_tail"]) == (None, None, None)


def test_create_writes_platform_shop_id(engine, admin):
    sid = admin.create("店A", platform_shop_id="100000001")
    assert _profile(engine, sid)["platform_shop_id"] == "100000001"


def test_create_with_bad_platform_shop_id_creates_nothing(engine, admin):
    with pytest.raises(InvalidRequest):
        admin.create("店A", platform_shop_id="不是数字")
    with engine.connect() as conn:
        assert shop_store.list(conn) == []


def test_profile_edit_audit_records_field_names_only(engine, admin):
    sid = admin.create("店A")
    admin.update(sid, platform_shop_id="100000001", bank_tail="0000", actor="admin")
    (row,) = _audits(engine, "shop.profile_edit")
    assert row["actor"] == "admin" and row["shop_id"] == sid
    assert json.loads(row["req_summary"]) == {"fields": ["bank_tail", "platform_shop_id"]}
    summaries = f"{row['req_summary']} {row['resp_summary']}"
    assert "100000001" not in summaries and "0000" not in summaries


def test_profile_edit_audit_skips_unchanged_and_name_only(engine, admin):
    sid = admin.create("店A")
    admin.update(sid, bank_tail="0000")
    admin.update(sid, bank_tail="0000")  # 值没变
    admin.update(sid, name="改名")  # 只改别名，不算收款信息
    assert len(_audits(engine, "shop.profile_edit")) == 1


def test_profile_edit_audit_includes_entity(engine, admin):
    sid = admin.create("店A")
    admin.update(sid, entity="示例商贸有限公司")
    admin.update(sid, entity="")
    rows = _audits(engine, "shop.profile_edit")
    assert [json.loads(r["req_summary"])["fields"] for r in rows] == [["entity"], ["entity"]]
    assert "示例商贸" not in json.dumps(rows, ensure_ascii=False)
