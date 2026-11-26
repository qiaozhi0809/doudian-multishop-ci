"""飞鸽会话视图的纯规则：买家显示名、等待计时、快捷筛选、计数、排序与分页。

会话来自内存快照（不落库），跨店合并后在这里筛完、排完再分页。时间一律 UTC ISO 字符串，
`now` 须带时区。
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.domain.im_rules import overdue_count
from app.shared.time_bj import BEIJING

ImQuick = Literal["unread", "waiting", "overdue", "today"]
ImConversationSort = Literal["waiting", "last_at", "unread", "shop_name"]
SortOrder = Literal["asc", "desc"]

_TAIL_DIGITS = 4


@dataclass(frozen=True)
class ConvRow:
    shop_id: int
    shop_name: str
    conversation_id: str
    buyer: str = field(repr=False)  # 可能是买家昵称，不进日志
    preview: str = field(repr=False)  # 消息正文，不进日志
    unread: int
    last_at: str | None
    waiting_since: str | None


def buyer_label(conversation_id: str, buyer_name: str | None) -> str:
    """有昵称用昵称，否则用会话 short ID 后 4 位区分。"""
    return buyer_name or f"买家 · 尾号 {conversation_id[-_TAIL_DIGITS:]}"


# ---- 计时 ----


def wait_seconds(row: ConvRow, now: datetime) -> int | None:
    """买家已等待的整秒数；没在等返回 None。平台时钟略快于本机时记 0。"""
    if row.waiting_since is None:
        return None
    waited = now - datetime.fromisoformat(row.waiting_since)
    return max(int(waited.total_seconds()), 0)


def is_overdue(row: ConvRow, now: datetime) -> bool:
    """与「超 3 分钟未回复」通知同一判定（im_rules.overdue_count）。"""
    return overdue_count({row.conversation_id: row.waiting_since}, now) > 0


def is_today(last_at: str | None, now: datetime) -> bool:
    """最后一条消息是否在北京时间的今天。"""
    if last_at is None:
        return False
    sent = datetime.fromisoformat(last_at).astimezone(BEIJING)
    return sent.date() == now.astimezone(BEIJING).date()


# ---- 筛选与计数 ----


QUICK_FILTERS: dict[ImQuick, Callable[[ConvRow, datetime], bool]] = {
    "unread": lambda row, now: row.unread > 0,
    "waiting": lambda row, now: row.waiting_since is not None,
    "overdue": is_overdue,
    "today": lambda row, now: is_today(row.last_at, now),
}


def matches(row: ConvRow, *, unread_only: bool, quick: ImQuick | None, now: datetime) -> bool:
    if unread_only and not QUICK_FILTERS["unread"](row, now):
        return False
    return quick is None or QUICK_FILTERS[quick](row, now)


def counts(rows: Sequence[ConvRow], now: datetime) -> dict[ImQuick, int]:
    """计数卡：调用方只按店铺筛过，不受当前快捷筛选与「只看未读」影响。"""
    return {key: sum(hit(row, now) for row in rows) for key, hit in QUICK_FILTERS.items()}


# ---- 排序与分页 ----

# 排序键返回 None 表示该行没有这一项：升降序都排在后面
SORT_KEYS: dict[ImConversationSort, Callable[[ConvRow, datetime], int | str | None]] = {
    "waiting": wait_seconds,
    "last_at": lambda row, now: row.last_at,
    "unread": lambda row, now: row.unread,
    "shop_name": lambda row, now: row.shop_name,
}


def sort_rows(
    rows: Sequence[ConvRow], sort: ImConversationSort | None, order: SortOrder, now: datetime
) -> list[ConvRow]:
    """省略 sort = 等待时间倒序（不看 order）。

    没有排序值的行（没在等待）排在后面、按最后消息时间倒序；同值按 (shop_id, conversation_id)。
    """
    if sort is None:
        sort, order = "waiting", "desc"
    key = SORT_KEYS[sort]
    # 逐级稳定排序：先排兜底次序，再排主键；reverse 不打乱同值行的相对次序
    stable = sorted(rows, key=lambda row: (row.shop_id, row.conversation_id))
    present = [row for row in stable if key(row, now) is not None]
    missing = [row for row in stable if key(row, now) is None]
    present.sort(key=lambda row: key(row, now), reverse=order == "desc")
    missing.sort(key=lambda row: row.last_at or "", reverse=True)
    return present + missing


def page_rows(rows: Sequence[ConvRow], page: int, page_size: int) -> tuple[list[ConvRow], int]:
    """page 从 1 起；返回（本页, 总数）。"""
    start = (page - 1) * page_size
    return list(rows[start : start + page_size]), len(rows)
