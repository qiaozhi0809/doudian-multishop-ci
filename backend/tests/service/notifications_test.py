"""通知服务：事件合并、强状态去重 / 静默重开 / 恢复、汇总与已读。"""

from datetime import timedelta

import pytest

from app.service.events import NOTIFICATION, EventBus
from app.service.notifications import NotificationService
from tests.service.label_support import add_shop


@pytest.fixture
def published():
    return []


@pytest.fixture
def svc(engine, clock, published):
    events = EventBus()
    original = events.publish

    def record(event, data):
        if event == NOTIFICATION:
            published.append(data)
        original(event, data)

    events.publish = record
    return NotificationService(engine, events, clock=clock)


@pytest.fixture
def shop_a(engine):
    return add_shop(engine, name="店A")


def _rows(svc, kind=None):
    items = svc.list(unread_only=False, page=1)["items"]
    return [r for r in items if kind is None or r["kind"] == kind]


def test_emit_merges_unread_same_shop_kind(svc, shop_a, clock, published):
    first = svc.emit("new_order", shop_id=shop_a, count=3)
    clock.now += timedelta(minutes=1)
    second = svc.emit("new_order", shop_id=shop_a, count=4)

    assert first == second
    rows = _rows(svc)
    assert len(rows) == 1
    assert rows[0]["count"] == 7 and rows[0]["title"] == "店A 新增 7 单待发货"
    assert rows[0]["updated_at"] == "2026-12-01T00:01:00Z"
    assert rows[0]["link"] == f"/orders?shops={shop_a}" and rows[0]["level"] == "medium"
    assert [p["action"] for p in published] == ["created", "updated"]
    # 未读时又来新单：合并后数量变多也要再提醒（前端按 id + 数量去重）
    assert published[0]["alert"] is True and published[1]["alert"] is True
    assert published[1]["item"]["count"] == 7


def test_merge_alerts_again_only_for_new_items(svc, shop_a, published):
    svc.emit("new_aftersale", shop_id=shop_a, count=1)
    svc.emit("new_aftersale", shop_id=shop_a, count=1)
    svc.emit("sync_failed", shop_id=shop_a, detail="orders")
    svc.emit("sync_failed", shop_id=shop_a, detail="orders")
    assert [(p["item"]["kind"], p["action"], p["alert"]) for p in published] == [
        ("new_aftersale", "created", True), ("new_aftersale", "updated", True),
        ("sync_failed", "created", True), ("sync_failed", "updated", False)]


def test_emit_after_read_creates_new(svc, shop_a):
    first = svc.emit("new_order", shop_id=shop_a, count=3)
    svc.mark_read(first)
    second = svc.emit("new_order", shop_id=shop_a, count=2)
    assert first != second and len(_rows(svc)) == 2


def test_emit_without_shop_never_merges(svc):
    a = svc.emit("batch_failed", shop_id=None, count=5, detail="2")
    b = svc.emit("batch_failed", shop_id=None, count=1, detail="1")
    assert a != b
    assert {r["title"] for r in _rows(svc)} == {
        "打单完成：成功 5，失败 2", "打单完成：成功 1，失败 1"}


def test_raise_state_twice_one_row_second_silent(svc, shop_a, published):
    svc.raise_state("egress", "egress_unreachable", shop_id=shop_a, detail="连接超时")
    svc.raise_state("egress", "egress_unreachable", shop_id=shop_a, detail="连接被拒绝")

    rows = _rows(svc)
    assert len(rows) == 1
    assert rows[0]["state_key"] == f"egress:{shop_a}" and rows[0]["body"] == "连接被拒绝"
    assert rows[0]["title"] == "店A 出口不通" and rows[0]["level"] == "strong"
    assert [(p["action"], p["alert"]) for p in published] == [
        ("created", True), ("updated", False)]


def test_resolve_writes_recovered_with_original_link(svc, shop_a, published):
    svc.raise_state("login", "login_expired", shop_id=shop_a)
    svc.resolve_state("login", shop_id=shop_a)

    state = _rows(svc, "login_expired")[0]
    assert state["resolved_at"] == "2026-12-01T00:00:00Z"
    recovered = _rows(svc, "recovered")
    assert len(recovered) == 1
    assert recovered[0]["title"] == "店A 已恢复：登录失效"
    assert recovered[0]["link"] == state["link"] and recovered[0]["level"] == "weak"
    assert [p["action"] for p in published] == ["created", "resolved", "created"]
    assert published[1]["alert"] is False


def test_resolve_without_open_state_is_noop(svc, shop_a, published):
    svc.resolve_state("risk", shop_id=shop_a)
    assert _rows(svc) == [] and published == []


def test_reraise_within_30min_reopens_silently(svc, shop_a, clock, published):
    """Review Focus 1：30 分钟内再犯 → 同一条重开、静默，再恢复也不写第二条「已恢复」。"""
    svc.raise_state("egress", "egress_unreachable", shop_id=shop_a)
    first_id = _rows(svc, "egress_unreachable")[0]["id"]
    svc.resolve_state("egress", shop_id=shop_a)
    clock.now += timedelta(minutes=10)
    published.clear()

    svc.raise_state("egress", "egress_unreachable", shop_id=shop_a, detail="又断了")

    states = _rows(svc, "egress_unreachable")
    assert len(states) == 1 and states[0]["id"] == first_id
    assert states[0]["resolved_at"] is None and states[0]["body"] == "又断了"
    assert [(p["action"], p["alert"]) for p in published] == [("updated", False)]

    clock.now += timedelta(minutes=5)
    svc.resolve_state("egress", shop_id=shop_a)
    assert len(_rows(svc, "recovered")) == 1


def test_reopened_twice_still_single_recovered(svc, shop_a, clock):
    for _ in range(3):
        svc.raise_state("risk", "risk_paused", shop_id=shop_a)
        svc.resolve_state("risk", shop_id=shop_a)
        clock.now += timedelta(minutes=5)
    assert len(_rows(svc, "risk_paused")) == 1
    assert len(_rows(svc, "recovered")) == 1


def test_reraise_after_31min_is_new_alert(svc, shop_a, clock, published):
    svc.raise_state("egress", "egress_unreachable", shop_id=shop_a)
    svc.resolve_state("egress", shop_id=shop_a)
    clock.now += timedelta(minutes=31)
    published.clear()

    svc.raise_state("egress", "egress_unreachable", shop_id=shop_a)

    assert len(_rows(svc, "egress_unreachable")) == 2
    assert [(p["action"], p["alert"]) for p in published] == [("created", True)]
    svc.resolve_state("egress", shop_id=shop_a)
    assert len(_rows(svc, "recovered")) == 2


def test_other_family_recovery_does_not_suppress(svc, shop_a, clock):
    """另一类问题的「已恢复」不能让本类恢复被误判为静默重开。"""
    svc.raise_state("login", "login_expired", shop_id=shop_a)
    clock.now += timedelta(minutes=1)
    svc.raise_state("egress", "egress_unreachable", shop_id=shop_a)
    svc.resolve_state("egress", shop_id=shop_a)
    svc.resolve_state("login", shop_id=shop_a)
    titles = {r["title"] for r in _rows(svc, "recovered")}
    assert titles == {"店A 已恢复：出口不通", "店A 已恢复：登录失效"}


def test_deadline_count_and_recovered_label(svc, shop_a):
    svc.raise_state("deadline", "ship_deadline", shop_id=shop_a, count=3)
    svc.raise_state("deadline", "ship_deadline", shop_id=shop_a, count=5)
    row = _rows(svc, "ship_deadline")[0]
    assert row["count"] == 5 and row["title"] == "店A 5 单临近发货超时"
    svc.resolve_state("deadline", shop_id=shop_a)
    assert _rows(svc, "recovered")[0]["title"] == "店A 已恢复：临近发货超时"


def test_summary_groups_strong_open_by_shop(svc, engine, shop_a):
    shop_b = add_shop(engine, name="店B")
    svc.raise_state("login", "login_expired", shop_id=shop_a)
    svc.raise_state("egress", "egress_unreachable", shop_id=shop_a)
    svc.raise_state("risk", "risk_paused", shop_id=shop_b)
    svc.resolve_state("risk", shop_id=shop_b)
    svc.emit("new_order", shop_id=shop_a, count=1)

    s = svc.summary()

    assert s["strong_open"] == [{
        "shop_id": shop_a, "shop_name": "店A",
        "kinds": ["login_expired", "egress_unreachable"], "link": f"/shops?shop={shop_a}",
        "problems": [
            {"kind": "login_expired", "link": f"/shops?shop={shop_a}"},
            {"kind": "egress_unreachable", "link": f"/shops?shop={shop_a}"},
        ],
    }]
    # 未解决的强状态由横条 / 待处理代表，不计未读：已解决的风控 + 已恢复 + 新订单
    assert s["unread"] == 3


def test_summary_problem_links_per_kind(svc, shop_a):
    svc.raise_state("login", "login_expired", shop_id=shop_a)
    svc.raise_state("deadline", "ship_deadline", shop_id=shop_a, count=2)
    (group,) = svc.summary()["strong_open"]
    assert group["problems"] == [
        {"kind": "login_expired", "link": f"/shops?shop={shop_a}"},
        {"kind": "ship_deadline", "link": f"/orders?quick=exp_ship&shops={shop_a}"},
    ]


def test_unread_excludes_open_states_until_resolved(svc, shop_a):
    svc.raise_state("login", "login_expired", shop_id=shop_a)
    assert svc.summary()["unread"] == 0
    svc.resolve_state("login", shop_id=shop_a)
    assert svc.summary()["unread"] == 2  # 已解决的登录失效 + 已恢复


def test_raise_state_unchanged_is_noop(svc, shop_a, clock, published):
    svc.raise_state("egress", "egress_unreachable", shop_id=shop_a, detail="直连不通")
    clock.now += timedelta(minutes=5)
    svc.raise_state("egress", "egress_unreachable", shop_id=shop_a, detail="直连不通")
    assert [p["action"] for p in published] == ["created"]
    assert _rows(svc)[0]["updated_at"] == "2026-12-01T00:00:00Z"


def test_raise_state_link_override_updates_row(svc, shop_a, published):
    svc.raise_state("deadline", "ship_deadline", shop_id=shop_a, count=1)
    svc.raise_state("deadline", "ship_deadline", shop_id=shop_a, count=1,
                    link=f"/orders?quick=ship_delay&shops={shop_a}")
    assert _rows(svc)[0]["link"] == f"/orders?quick=ship_delay&shops={shop_a}"
    assert [(p["action"], p["alert"]) for p in published] == [
        ("created", True), ("updated", False)]


def test_mark_all_read(svc, shop_a, published):
    svc.emit("new_order", shop_id=shop_a)
    svc.raise_state("login", "login_expired", shop_id=shop_a)
    published.clear()

    svc.mark_all_read()

    assert svc.summary()["unread"] == 0
    assert [p["action"] for p in published] == ["read"]
    assert published[0]["alert"] is False
    assert svc.list(unread_only=True, page=1)["items"] == []
    assert len(svc.summary()["strong_open"]) == 1  # 已读不等于已解决


def test_mark_read_single(svc, shop_a, published):
    nid = svc.emit("new_order", shop_id=shop_a)
    published.clear()
    svc.mark_read(nid)
    assert published[0]["action"] == "read" and published[0]["item"]["id"] == nid
    assert published[0]["item"]["read_at"] == "2026-12-01T00:00:00Z"
    assert svc.summary()["unread"] == 0


def test_list_paging(svc, engine, clock):
    shops = [add_shop(engine, name=f"店{i}") for i in range(3)]
    for sid in shops:
        svc.emit("new_order", shop_id=sid)
        clock.now += timedelta(minutes=1)
    page = svc.list(unread_only=False, page=2, page_size=2)
    assert page["total"] == 3 and page["page"] == 2 and page["page_size"] == 2
    assert [r["shop_id"] for r in page["items"]] == [shops[0]]


def test_purge_removes_read_events_older_than_30_days(svc, shop_a, clock):
    old = svc.emit("new_order", shop_id=shop_a)
    svc.mark_read(old)
    svc.raise_state("login", "login_expired", shop_id=shop_a)
    svc.mark_all_read()
    clock.now += timedelta(days=31)
    fresh = svc.emit("sync_done", shop_id=shop_a, detail="orders")
    svc.mark_read(fresh)

    assert svc.purge(clock.now) == 1
    remaining = {r["kind"] for r in _rows(svc)}
    assert remaining == {"login_expired", "sync_done"}


def test_sync_failed_merges_only_same_sync_type(svc, shop_a):
    svc.emit("sync_failed", shop_id=shop_a, detail="orders")
    svc.emit("sync_failed", shop_id=shop_a, detail="aftersales")
    svc.emit("sync_failed", shop_id=shop_a, detail="orders")
    rows = {r["title"]: r for r in _rows(svc, "sync_failed")}
    assert set(rows) == {"店A 订单同步失败", "店A 售后同步失败"}
    assert rows["店A 订单同步失败"]["count"] == 2
    assert rows["店A 订单同步失败"]["link"] == f"/orders?shops={shop_a}"
    assert rows["店A 售后同步失败"]["count"] == 1


def test_recovered_marker_set_with_first_recovered(svc, shop_a):
    svc.raise_state("login", "login_expired", shop_id=shop_a)
    assert _rows(svc, "login_expired")[0]["recovered_notified_at"] is None
    svc.resolve_state("login", shop_id=shop_a)
    state = _rows(svc, "login_expired")[0]
    recovered = _rows(svc, "recovered")[0]
    assert state["recovered_notified_at"] == recovered["created_at"]


def test_reopen_suppression_survives_title_change(svc, shop_a, clock):
    """重开时问题换了说法（标题变了），再恢复仍不写第二条「已恢复」。"""
    svc.raise_state("egress", "egress_unreachable", shop_id=shop_a)
    svc.resolve_state("egress", shop_id=shop_a)
    clock.now += timedelta(minutes=10)
    svc.raise_state("egress", "egress_duplicate", shop_id=shop_a)
    assert _rows(svc, "egress_duplicate")[0]["title"] == "店A 出口 IP 与其他店重复"
    svc.resolve_state("egress", shop_id=shop_a)
    assert len(_rows(svc, "recovered")) == 1


def test_kind_change_within_family_updates_row(svc, shop_a, published):
    svc.raise_state("egress", "egress_unreachable", shop_id=shop_a, detail="连接超时")
    svc.raise_state("egress", "egress_changed", shop_id=shop_a, detail="IP 变了")
    rows = _rows(svc)
    assert len(rows) == 1
    assert rows[0]["kind"] == "egress_changed" and rows[0]["level"] == "strong"
    assert rows[0]["title"] == "店A 出口 IP 已变化" and rows[0]["body"] == "IP 变了"
    assert published[-1]["alert"] is False
    svc.resolve_state("egress", shop_id=shop_a)
    assert _rows(svc, "recovered")[0]["title"] == "店A 已恢复：出口 IP 已变化"


def test_list_clamps_page_and_size(svc, engine):
    for i in range(3):
        svc.emit("new_order", shop_id=add_shop(engine, name=f"店{i}"))
    assert svc.list(unread_only=False, page=0, page_size=0)["page"] == 1
    small = svc.list(unread_only=False, page=-3, page_size=0)
    assert small["page_size"] == 1 and len(small["items"]) == 1
    assert svc.list(unread_only=False, page=1, page_size=10_000)["page_size"] == 200
