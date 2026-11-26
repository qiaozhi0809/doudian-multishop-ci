"""事件翻译：业务事件 → 通知（状态对账、临近超时分组、批量结果、新单 / 同步结果）。"""

import asyncio

import pytest
import sqlalchemy as sa

from app.service.events import (
    AFTERSALES_NEW,
    LABEL_DONE,
    ORDERS_NEW,
    PRINT_DONE,
    RECONCILE_DONE,
    SHIP_DEADLINE_WARNING,
    SHIP_DONE,
    SHOP_LOGIN_FAILED,
    SHOP_STATUS_CHANGED,
    SYNC_RESULT,
    EventBus,
)
from app.service.notification_feed import NotificationFeed
from app.service.notifications import NotificationService
from app.store import session_store
from app.store.schema import shop
from app.store.session_store import SessionRow
from tests.service.label_support import add_shop

NOW = "2026-12-01T00:00:00Z"


@pytest.fixture
def svc(engine, clock):
    return NotificationService(engine, EventBus(), clock=clock)


@pytest.fixture
def feed(engine, svc):
    return NotificationFeed(engine, svc)


@pytest.fixture
def shop_a(engine):
    return add_shop(engine, name="店A")


@pytest.fixture
def shop_b(engine):
    return add_shop(engine, name="店B")


def rows(svc, kind=None):
    items = svc.list(unread_only=False, page=1)["items"]
    return [r for r in items if kind is None or r["kind"] == kind]


def set_shop(engine, shop_id, **values):
    with engine.begin() as conn:
        conn.execute(sa.update(shop).where(shop.c.id == shop_id).values(**values))


def save_session(engine, shop_id):
    with engine.begin() as conn:
        session_store.save(conn, SessionRow(shop_id, b"c", b"t", "{}", None), NOW)


# ---- 状态对账 ----

def test_egress_unreachable_then_ok_resolves_with_recovered(feed, svc, engine, shop_a):
    set_shop(engine, shop_a, egress_status="unreachable")
    feed.handle(SHOP_STATUS_CHANGED, {"shop_id": shop_a, "egress_status": "unreachable"})
    (open_row,) = rows(svc, "egress_unreachable")
    assert open_row["state_key"] == f"egress:{shop_a}" and open_row["resolved_at"] is None

    set_shop(engine, shop_a, egress_status="ok")
    feed.handle(SHOP_STATUS_CHANGED, {"shop_id": shop_a, "egress_status": "ok"})
    (resolved,) = rows(svc, "egress_unreachable")
    assert resolved["resolved_at"] is not None
    (recovered,) = rows(svc, "recovered")
    assert recovered["title"] == "店A 已恢复：出口不通"


def test_egress_kind_follows_shop_row_not_payload(feed, svc, engine, shop_a):
    set_shop(engine, shop_a, egress_status="duplicate")
    feed.handle(SHOP_STATUS_CHANGED, {"shop_id": shop_a})  # 载荷不带出口字段
    assert [r["kind"] for r in rows(svc)] == ["egress_duplicate"]


def test_needs_login_with_session_reports_and_login_resolves(feed, svc, engine, shop_a):
    save_session(engine, shop_a)
    set_shop(engine, shop_a, status="needs_login")
    feed.handle(SHOP_LOGIN_FAILED, {"shop_id": shop_a, "reason": "扫码超时"})
    (row,) = rows(svc, "login_expired")
    assert row["title"] == "店A 登录失效" and row["resolved_at"] is None

    set_shop(engine, shop_a, status="active")
    feed.handle(SHOP_STATUS_CHANGED, {"shop_id": shop_a, "status": "active"})
    assert rows(svc, "login_expired")[0]["resolved_at"] is not None


def test_never_logged_in_shop_needs_login(feed, svc, engine):
    sid = add_shop(engine, name="店新", status="needs_login")
    feed.handle(SHOP_STATUS_CHANGED, {"shop_id": sid, "status": "needs_login"})
    assert rows(svc) == []


def test_risk_pause_raises_and_resume_resolves(feed, svc, engine, shop_a):
    set_shop(engine, shop_a, paused_reason="risk_blocked:50002")
    feed.handle(SHOP_STATUS_CHANGED, {"shop_id": shop_a, "paused_reason": "risk_blocked:50002"})
    (row,) = rows(svc, "risk_paused")
    assert row["resolved_at"] is None

    set_shop(engine, shop_a, paused_reason="manual")  # 非风控暂停：风控问题视为已解决
    feed.handle(SHOP_STATUS_CHANGED, {"shop_id": shop_a})
    assert rows(svc, "risk_paused")[0]["resolved_at"] is not None


def test_disabled_shop_resolves_all_states(feed, svc, engine, shop_a):
    save_session(engine, shop_a)
    set_shop(engine, shop_a, status="needs_login", egress_status="unreachable")
    feed.handle(SHOP_STATUS_CHANGED, {"shop_id": shop_a})
    assert len([r for r in rows(svc) if r["state_key"]]) == 2
    set_shop(engine, shop_a, status="disabled")
    feed.handle(SHOP_STATUS_CHANGED, {"shop_id": shop_a})
    assert all(r["resolved_at"] for r in rows(svc) if r["state_key"])


# ---- 临近超时 ----

def deadline_event(*shop_ids):
    items = [{"shop_id": s, "order_no": f"no-{i}"} for i, s in enumerate(shop_ids)]
    counts: dict[int, int] = {}
    for s in shop_ids:
        counts[s] = counts.get(s, 0) + 1
    return {"count": len(items), "items": items, "shop_counts": counts}


def test_deadline_uses_shop_counts_not_capped_items(feed, svc, shop_a, shop_b):
    """items 被截到上限，只含店A；shop_counts 是真实分店计数，店B 不能被误判恢复。"""
    feed.handle(SHIP_DEADLINE_WARNING, deadline_event(shop_a, shop_b))
    capped = {"count": 2, "items": [{"shop_id": shop_a, "order_no": "x"}] * 2,
              "shop_counts": {str(shop_a): 150, str(shop_b): 120}}  # 经 JSON 时键为字符串
    feed.handle(SHIP_DEADLINE_WARNING, capped)
    by_shop = {r["shop_id"]: r for r in rows(svc, "ship_deadline")}
    assert by_shop[shop_a]["count"] == 150 and by_shop[shop_b]["count"] == 120
    assert by_shop[shop_b]["resolved_at"] is None
    assert rows(svc, "recovered") == []


def test_deadline_groups_by_shop_and_resolves_missing(feed, svc, shop_a, shop_b):
    feed.handle(SHIP_DEADLINE_WARNING, deadline_event(shop_a, shop_a, shop_b))
    by_shop = {r["shop_id"]: r for r in rows(svc, "ship_deadline")}
    assert by_shop[shop_a]["count"] == 2 and by_shop[shop_b]["count"] == 1
    assert by_shop[shop_a]["title"] == "店A 2 单临近发货超时"

    feed.handle(SHIP_DEADLINE_WARNING, deadline_event(shop_a))
    by_shop = {r["shop_id"]: r for r in rows(svc, "ship_deadline")}
    assert by_shop[shop_a]["resolved_at"] is None and by_shop[shop_a]["count"] == 1
    assert by_shop[shop_b]["resolved_at"] is not None


# ---- 批量结果 ----

def test_label_done_with_failure_is_batch_failed(feed, svc):
    feed.handle(LABEL_DONE, {"preview_id": "p1", "mode": "obtain", "ok": 3, "failed": 1})
    (row,) = rows(svc)
    assert row["kind"] == "batch_failed" and row["title"] == "打单完成：成功 3，失败 1"


def test_batch_titles_distinguish_operation(feed, svc):
    feed.handle(SHIP_DONE, {"batch_id": "b1", "ok": 2, "failed": 0, "skipped": 0})
    feed.handle(PRINT_DONE, {"ok": 1, "failed": 2, "manual": 0, "skipped": 0})
    feed.handle(LABEL_DONE, {"preview_id": "p2", "mode": "void", "ok": 1, "failed": 0})
    titles = {r["title"]: r["kind"] for r in rows(svc)}
    assert titles == {
        "发货完成：成功 2": "batch_done",
        "打印完成：成功 1，失败 2": "batch_failed",
        "作废面单完成：成功 1": "batch_done",
    }


def test_verifying_and_manual_count_as_follow_up(feed, svc):
    feed.handle(LABEL_DONE, {"preview_id": "p3", "mode": "obtain", "ok": 12, "failed": 1,
                             "verifying": 2, "skipped": 0})
    feed.handle(PRINT_DONE, {"ok": 8, "failed": 0, "manual": 1, "skipped": 0})
    feed.handle(LABEL_DONE, {"preview_id": "p4", "mode": "obtain", "ok": 1, "failed": 0,
                             "verifying": 1})
    titles = {r["title"]: r["kind"] for r in rows(svc)}
    assert titles == {
        "打单完成：成功 12，失败 1，待核实 2": "batch_failed",
        "打印完成：成功 8，需补打 1": "batch_failed",
        "打单完成：成功 1，待核实 1": "batch_failed",
    }


def test_simulated_batch_not_notified(feed, svc):
    feed.handle(SHIP_DONE, {"batch_id": "dry-1", "ok": 0, "failed": 0, "simulated": True})
    assert rows(svc) == []


def test_reconcile_done(feed, svc):
    feed.handle(RECONCILE_DONE, {"run_id": "r1", "status": "success", "findings": 0})
    assert [r["kind"] for r in rows(svc)] == ["reconcile_done"]


def test_failed_reconcile_not_announced(feed, svc):
    feed.handle(RECONCILE_DONE, {"run_id": "r2", "status": "failed", "errors": 2})
    assert rows(svc) == []


def test_sync_failed_carries_reason_in_body(feed, svc, shop_a):
    feed.handle(SYNC_RESULT, {"kind": "orders", "shop_id": shop_a, "ok": False,
                              "error": "该店铺需要重新扫码登录"})
    feed.handle(SYNC_RESULT, {"kind": "orders", "shop_id": shop_a, "ok": False,
                              "error": "内部错误"})
    (row,) = rows(svc, "sync_failed")
    assert row["count"] == 2 and row["body"] == "内部错误"  # 合并后正文为最近一次原因


def test_egress_body_names_concrete_problem(feed, svc, engine, shop_a, shop_b):
    set_shop(engine, shop_a, egress_status="unreachable", egress_mode="direct")
    set_shop(engine, shop_b, egress_ip="203.0.113.9")
    feed.handle(SHOP_STATUS_CHANGED, {"shop_id": shop_a})
    assert rows(svc, "egress_unreachable")[0]["body"] == "直连不通"
    set_shop(engine, shop_a, egress_status="duplicate", egress_ip_pending="203.0.113.9")
    feed.handle(SHOP_STATUS_CHANGED, {"shop_id": shop_a})
    (row,) = [r for r in rows(svc) if r["state_key"] == f"egress:{shop_a}"]
    assert row["kind"] == "egress_duplicate" and row["body"] == "与 店B 相同"
    assert "203.0.113" not in (row["body"] or "")


# ---- 新单 / 同步结果 ----

def test_new_orders_and_aftersales(feed, svc, shop_a):
    feed.handle(ORDERS_NEW, {"shop_id": shop_a, "count": 5})
    feed.handle(AFTERSALES_NEW, {"shop_id": shop_a, "count": 2})
    titles = sorted(r["title"] for r in rows(svc))
    assert titles == ["店A 新增 2 个售后", "店A 新增 5 单待发货"]


def test_sync_result_done_and_failed(feed, svc, shop_a):
    feed.handle(SYNC_RESULT, {"kind": "stock", "shop_id": shop_a, "ok": True, "error": None})
    feed.handle(SYNC_RESULT, {"kind": "fund", "shop_id": shop_a, "ok": False, "error": "x"})
    by_kind = {r["kind"]: r for r in rows(svc)}
    assert by_kind["sync_done"]["title"] == "店A 库存同步完成"
    assert by_kind["sync_failed"]["title"] == "店A 资金同步失败"
    assert by_kind["sync_failed"]["link"] == f"/fund?shops={shop_a}"


def test_unknown_event_ignored(feed, svc):
    feed.handle("label_progress", {"x": 1})
    assert rows(svc) == []


# ---- 订阅循环 ----

async def test_run_survives_handler_error_and_stops(engine, svc, shop_a, monkeypatch):
    feed = NotificationFeed(engine, svc)
    bus = EventBus()
    stop = asyncio.Event()
    calls = []
    original = feed.handle

    def flaky(event, data):
        calls.append(event)
        if event == RECONCILE_DONE:
            raise RuntimeError("boom")
        original(event, data)

    monkeypatch.setattr(feed, "handle", flaky)
    task = asyncio.create_task(feed.run(bus, stop))
    await asyncio.sleep(0)  # 让订阅生效
    bus.publish(RECONCILE_DONE, {"run_id": "r"})
    bus.publish(ORDERS_NEW, {"shop_id": shop_a, "count": 1})
    for _ in range(100):
        if rows(svc, "new_order"):
            break
        await asyncio.sleep(0.01)
    assert [r["kind"] for r in rows(svc)] == ["new_order"]
    stop.set()
    await asyncio.wait_for(task, 1)
    assert calls[:2] == [RECONCILE_DONE, ORDERS_NEW]
    assert bus.subscriber_count == 0
