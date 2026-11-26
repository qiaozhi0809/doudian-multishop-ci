"""飞鸽会话查询：跨店合并内存快照后筛选、排序、分页与计数；消息记录读 im_message 表。

只读。须在事件循环线程里调用（快照由接收任务在同一个循环里维护）。
买家昵称与消息正文只交给接口层返回，不进日志、审计、事件。
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import Engine

from app.adapter.flybird.parse import SenderRole
from app.domain import im_view_rules as rules
from app.domain.errors import NotFound
from app.domain.im_view_rules import ConvRow, ImConversationSort, ImQuick, SortOrder
from app.service.im_watcher import ImWatcher
from app.store import im_message_store, shop_store

_NOT_FOUND = "会话不存在"


@dataclass(frozen=True)
class ThreadMessage:
    message_id: str
    sender_role: SenderRole
    text: str = field(repr=False)  # 正文不进日志
    sent_at: str


@dataclass(frozen=True)
class ImThreadData:
    shop_id: int
    conversation_id: str
    items: list[ThreadMessage]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ImQueryService:
    def __init__(
        self, engine: Engine, im: ImWatcher, *, clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._engine = engine
        self._im = im
        self._clock = clock

    def now(self) -> datetime:
        """一次请求取一次：筛选、排序与返回的等待秒数用同一个时刻。"""
        return self._clock()

    def rows(self, shop_ids: Sequence[int]) -> list[ConvRow]:
        """按 shop_ids 的顺序合并各店快照；没在接收的店没有行。"""
        with self._engine.connect() as conn:
            names = {s["id"]: s["name"] for s in shop_store.list(conn)}
        return [
            ConvRow(
                shop_id, names.get(shop_id, ""), view.conversation_id,
                rules.buyer_label(view.conversation_id, view.buyer_name),
                view.last_text, view.pending, view.last_at, view.waiting_since,
            )
            for shop_id in shop_ids
            for view in self._im.snapshot(shop_id)
        ]

    def conversations(
        self, shop_ids: Sequence[int], *, unread_only: bool, quick: ImQuick | None,
        sort: ImConversationSort | None, order: SortOrder, page: int, page_size: int,
        now: datetime | None = None,
    ) -> tuple[list[ConvRow], int]:
        """返回（本页, 筛选后总数）。"""
        now = now or self.now()
        hits = [
            row for row in self.rows(shop_ids)
            if rules.matches(row, unread_only=unread_only, quick=quick, now=now)
        ]
        return rules.page_rows(rules.sort_rows(hits, sort, order, now), page, page_size)

    def counts(self, shop_ids: Sequence[int]) -> dict[ImQuick, int]:
        return rules.counts(self.rows(shop_ids), self.now())

    def thread(self, shop_id: int, conversation_id: str) -> ImThreadData:
        """该会话已采集的消息，按发送时间正序；快照里有但还没存到消息时为空。"""
        with self._engine.connect() as conn:
            stored = im_message_store.list_for_conversation(conn, shop_id, conversation_id)
        if not stored and all(
            view.conversation_id != conversation_id for view in self._im.snapshot(shop_id)
        ):
            raise NotFound(_NOT_FOUND, shop_id)
        items = [
            ThreadMessage(r["message_id"], r["sender_role"], r["text"], r["sent_at"])
            for r in stored
        ]
        return ImThreadData(shop_id, conversation_id, items)
