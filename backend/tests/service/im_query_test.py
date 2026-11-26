"""飞鸽会话查询：跨店合并内存快照、筛排分页、计数、消息记录。数据全部虚构。"""

from datetime import timedelta

import pytest

from app.domain.errors import NotFound
from app.service.im_query import ImQueryService
from app.service.im_session import ConvView
from app.store import im_message_store, shop_store
from tests.service.im_session_test import START

NOW_AT = START  # 2026-12-01T02:00:00Z


def at(seconds_ago: int) -> str:
    return (NOW_AT - timedelta(seconds=seconds_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def view(
    conv: str = "conv-test-1", *, text: str = "在吗", last: int = 60, pending: int = 0,
    waiting: int | None = None, name: str | None = "测试买家",
) -> ConvView:
    """last / waiting：距现在多少秒。"""
    return ConvView(
        conv, None, text, "buyer", at(last), pending,
        None if waiting is None else at(waiting), name,
    )


class FakeIm:
    def __init__(self) -> None:
        self.views: dict[int, list[ConvView]] = {}

    def snapshot(self, shop_id: int) -> list[ConvView]:
        return list(self.views.get(shop_id, []))


@pytest.fixture
def shops(engine) -> tuple[int, int]:
    with engine.begin() as conn:
        return tuple(shop_store.create(conn, name, at(0)) for name in ("测试小铺", "测试小店"))


@pytest.fixture
def im() -> FakeIm:
    return FakeIm()


@pytest.fixture
def query(engine, im) -> ImQueryService:
    return ImQueryService(engine, im, clock=lambda: NOW_AT)


def save(engine, shop_id: int, conv: str, message_id: str, seconds_ago: int, text="在吗") -> None:
    with engine.begin() as conn:
        im_message_store.insert_ignore(conn, shop_id, [{
            "conversation_id": conv, "message_id": message_id, "sender_role": "buyer",
            "text": text, "sent_at": at(seconds_ago),
        }], at(0))


def listing(query, shop_ids, **kw):
    args = {"unread_only": False, "quick": None, "sort": None, "order": "desc",
            "page": 1, "page_size": 50} | kw
    return query.conversations(shop_ids, **args)


def test_rows_merge_shops(query, im, shops):
    first, second = shops
    im.views = {first: [view(pending=2, waiting=30)], second: [view("conv-test-2", name=None)]}

    rows = query.rows([first, second])

    assert [(r.shop_id, r.shop_name, r.conversation_id) for r in rows] == [
        (first, "测试小铺", "conv-test-1"), (second, "测试小店", "conv-test-2")]
    top = rows[0]
    assert (top.preview, top.unread, top.last_at, top.waiting_since) == (
        "在吗", 2, at(60), at(30))
    assert query.rows([second])[0].shop_id == second
    assert query.rows([]) == []


def test_buyer_uses_snapshot_name(query, im, shops):
    first, _ = shops
    im.views = {first: [view(), view("conv-test-5678", name=None)]}

    assert [r.buyer for r in query.rows([first])] == ["测试买家", "买家 · 尾号 5678"]


def test_conversations_filter_sort_page(query, im, shops):
    first, second = shops
    im.views = {
        first: [view("conv-test-1", pending=1, waiting=30), view("conv-test-2", last=5)],
        second: [view("conv-test-3", pending=1, waiting=300)],
    }

    rows, total = listing(query, [first, second])
    assert total == 3
    assert [r.conversation_id for r in rows] == ["conv-test-3", "conv-test-1", "conv-test-2"]

    rows, total = listing(query, [first, second], unread_only=True, page=2, page_size=1)
    assert (total, [r.conversation_id for r in rows]) == (2, ["conv-test-1"])

    rows, total = listing(query, [first, second], quick="overdue")
    assert (total, [r.conversation_id for r in rows]) == (1, ["conv-test-3"])

    rows, _ = listing(query, [first, second], sort="last_at", order="asc")
    assert [r.conversation_id for r in rows][-1] == "conv-test-2"


def test_counts_independent_of_quick(query, im, shops):
    first, second = shops
    im.views = {
        first: [view("conv-test-1", pending=1, waiting=30), view("conv-test-2")],
        second: [view("conv-test-3", pending=1, waiting=300)],
    }

    listing(query, [first, second], quick="overdue")

    assert query.counts([first, second]) == {
        "unread": 2, "waiting": 2, "overdue": 1, "today": 3}
    assert query.counts([second])["unread"] == 1


def test_thread_in_time_order(query, engine, shops):
    first, second = shops
    save(engine, first, "conv-test-1", "msg-test-2", 10, "还在吗")
    save(engine, first, "conv-test-1", "msg-test-1", 40)
    save(engine, second, "conv-test-1", "msg-test-3", 5, "别的店")

    thread = query.thread(first, "conv-test-1")

    assert (thread.shop_id, thread.conversation_id) == (first, "conv-test-1")
    assert [(m.message_id, m.sender_role, m.text, m.sent_at) for m in thread.items] == [
        ("msg-test-1", "buyer", "在吗", at(40)), ("msg-test-2", "buyer", "还在吗", at(10))]
    assert "在吗" not in repr(thread)


def test_thread_known_conversation_without_rows_is_empty(query, im, shops):
    first, _ = shops
    im.views = {first: [view()]}

    assert query.thread(first, "conv-test-1").items == []


def test_thread_unknown_conversation_not_found(query, im, engine, shops):
    first, second = shops
    im.views = {second: [view()]}
    save(engine, second, "conv-test-1", "msg-test-1", 5)

    with pytest.raises(NotFound) as error:
        query.thread(first, "conv-test-1")

    assert error.value.shop_id == first
