"""会话视图规则（纯函数）：买家显示名、等待计时、今日、筛选、计数、排序、分页。数据全部虚构。"""

from datetime import UTC, datetime, timedelta

import pytest

from app.domain.im_view_rules import (
    ConvRow,
    buyer_label,
    counts,
    is_overdue,
    is_today,
    matches,
    page_rows,
    sort_rows,
    wait_seconds,
)

NOW = datetime(2026, 12, 1, 2, 0, 0, tzinfo=UTC)  # 北京时间 10:00
DAY_S = 86400


def ago(seconds: int) -> str:
    return (NOW - timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


def row(
    conv: str = "1001",
    *,
    shop_id: int = 1,
    shop_name: str = "测试小铺",
    unread: int = 0,
    last: int | None = 0,
    waiting: int | None = None,
) -> ConvRow:
    """last / waiting：NOW 之前的秒数。"""
    return ConvRow(
        shop_id, shop_name, conv, "测试买家", "在吗", unread,
        None if last is None else ago(last), None if waiting is None else ago(waiting),
    )


def ids(rows: list[ConvRow]) -> list[str]:
    return [r.conversation_id for r in rows]


# ---- 买家显示名 ----


def test_buyer_label_name_or_last4():
    assert buyer_label("7000000000001001", "测试买家") == "测试买家"
    assert buyer_label("7000000000001001", None) == "买家 · 尾号 1001"
    assert buyer_label("1001", "") == "买家 · 尾号 1001"


def test_row_repr_hides_buyer_and_preview():
    text = repr(row())

    assert "测试买家" not in text and "在吗" not in text
    assert "1001" in text


# ---- 计时 ----


def test_wait_seconds_none_when_not_waiting():
    assert wait_seconds(row(), NOW) is None


def test_wait_seconds_counts_from_waiting_since():
    assert wait_seconds(row(waiting=75), NOW) == 75


def test_wait_seconds_never_negative():
    assert wait_seconds(row(waiting=-5), NOW) == 0  # 平台时钟略快于本机


@pytest.mark.parametrize(("waiting", "expected"), [(None, False), (180, False), (181, True)])
def test_overdue_boundary_3_minutes(waiting, expected):
    assert is_overdue(row(waiting=waiting), NOW) is expected


@pytest.mark.parametrize(("last_at", "now", "expected"), [
    ("2026-11-30T16:30:00Z", NOW, True),  # 北京今天 00:30
    ("2026-11-30T16:00:00Z", NOW, True),  # 北京今天 00:00
    ("2026-11-30T15:59:59Z", NOW, False),  # 北京昨天 23:59:59
    ("2026-12-01T10:00:00Z", datetime(2026, 12, 1, 17, 0, tzinfo=UTC), False),  # 北京已是次日
    (None, NOW, False),
])
def test_is_today_uses_beijing_day(last_at, now, expected):
    assert is_today(last_at, now) is expected


# ---- 筛选与计数 ----


@pytest.mark.parametrize(("quick", "hit", "miss"), [
    ("unread", row(unread=1), row()),
    ("waiting", row(waiting=10), row()),
    ("overdue", row(waiting=181), row(waiting=180)),
    ("today", row(last=0), row(last=DAY_S)),
])
def test_matches_each_quick(quick, hit, miss):
    assert matches(hit, unread_only=False, quick=quick, now=NOW)
    assert not matches(miss, unread_only=False, quick=quick, now=NOW)


def test_matches_without_filters():
    assert matches(row(last=None), unread_only=False, quick=None, now=NOW)


def test_unread_only_and_quick_combine():
    both = row(unread=2, waiting=200)
    only_overdue = row(unread=0, waiting=200)
    only_unread = row(unread=2, waiting=10)

    def hit(r: ConvRow) -> bool:
        return matches(r, unread_only=True, quick="overdue", now=NOW)

    assert [hit(both), hit(only_overdue), hit(only_unread)] == [True, False, False]
    assert not matches(row(), unread_only=True, quick=None, now=NOW)


def test_counts_ignore_quick():
    rows = [
        row("1001", unread=2, waiting=200),
        row("1002", unread=1, waiting=10),
        row("1003"),
        row("1004", last=DAY_S),
    ]

    assert counts(rows, NOW) == {"unread": 2, "waiting": 2, "overdue": 1, "today": 3}
    assert counts([], NOW) == {"unread": 0, "waiting": 0, "overdue": 0, "today": 0}


# ---- 排序与分页 ----


def test_default_sort_longest_wait_first_then_last_at():
    rows = [
        row("old", last=500),
        row("short", waiting=10, last=0),
        row("new", last=5),
        row("long", waiting=400, last=400),
    ]

    expected = ["long", "short", "new", "old"]
    assert ids(sort_rows(rows, None, "desc", NOW)) == expected
    assert ids(sort_rows(rows, None, "asc", NOW)) == expected  # 默认排序不看 order
    assert ids(sort_rows(rows, "waiting", "desc", NOW)) == expected


def test_sort_waiting_asc_keeps_non_waiting_last():
    rows = [row("old", last=500), row("long", waiting=400), row("new", last=5),
            row("short", waiting=10)]

    assert ids(sort_rows(rows, "waiting", "asc", NOW)) == ["short", "long", "new", "old"]


def test_sort_shop_name_and_unread_with_order():
    rows = [
        row("a", shop_name="测试小铺B", unread=1),
        row("b", shop_name="测试小铺A", unread=3),
        row("c", shop_name="测试小铺C", unread=2),
    ]

    assert ids(sort_rows(rows, "shop_name", "asc", NOW)) == ["b", "a", "c"]
    assert ids(sort_rows(rows, "shop_name", "desc", NOW)) == ["c", "a", "b"]
    assert ids(sort_rows(rows, "unread", "asc", NOW)) == ["a", "c", "b"]
    assert ids(sort_rows(rows, "unread", "desc", NOW)) == ["b", "c", "a"]


def test_sort_last_at_puts_missing_last_in_both_orders():
    rows = [row("none", last=None), row("old", last=500), row("new", last=5)]

    assert ids(sort_rows(rows, "last_at", "desc", NOW)) == ["new", "old", "none"]
    assert ids(sort_rows(rows, "last_at", "asc", NOW)) == ["old", "new", "none"]


@pytest.mark.parametrize("sort", [None, "waiting", "last_at", "unread", "shop_name"])
@pytest.mark.parametrize("order", ["asc", "desc"])
@pytest.mark.parametrize("waiting", [None, 60])
def test_sort_stable_ties(sort, order, waiting):
    rows = [
        row("1002", shop_id=2, waiting=waiting),
        row("1003", shop_id=1, waiting=waiting),
        row("1001", shop_id=2, waiting=waiting),
        row("1001", shop_id=1, waiting=waiting),
    ]

    for given in (rows, rows[::-1]):
        got = [(r.shop_id, r.conversation_id) for r in sort_rows(given, sort, order, NOW)]
        assert got == [(1, "1001"), (1, "1003"), (2, "1001"), (2, "1002")]


def test_sort_does_not_change_input():
    rows = [row("1002"), row("1001")]
    sort_rows(rows, None, "desc", NOW)

    assert ids(rows) == ["1002", "1001"]


@pytest.mark.parametrize(("page", "expected"), [
    (1, ["0", "1"]), (2, ["2", "3"]), (3, ["4"]), (4, []),
])
def test_page_rows_total(page, expected):
    rows = [row(str(i)) for i in range(5)]
    items, total = page_rows(rows, page, 2)

    assert (ids(items), total) == (expected, 5)
