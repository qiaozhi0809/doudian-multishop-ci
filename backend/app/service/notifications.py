"""通知中心统一入口：事件合并、强状态去重 / 静默重开 / 恢复，写库后发 `notification` 事件。

静默重开：强状态记录第一次写「已恢复」时，在同一事务里置 `recovered_notified_at`；
之后 30 分钟内重开再恢复，看到该列非空就不再写「已恢复」。
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Engine

from app.domain.notification_rules import (
    LEVEL_BY_KIND,
    REOPEN_SILENT_WITHIN,
    Kind,
    KindFamily,
    link_for,
    state_key,
    title_for,
)
from app.service.events import NOTIFICATION, EventBus
from app.store import notification_store, shop_store

ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
READ_RETENTION = timedelta(days=30)
_NO_MERGE: frozenset[str] = frozenset({"recovered"})  # 每条对应一个具体问题与链接
_MERGE_BY_LINK: frozenset[str] = frozenset({"sync_done", "sync_failed"})  # 链接区分同步类型
MAX_PAGE_SIZE = 200
_DEADLINE_LABEL = "临近发货超时"


def utc_now() -> datetime:
    return datetime.now(UTC)


def _fmt(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime(ISO_FMT)


def _parse(value: str) -> datetime:
    return datetime.strptime(value, ISO_FMT).replace(tzinfo=UTC)


def _shop_name(conn: sa.Connection, shop_id: int | None) -> str | None:
    if shop_id is None:
        return None
    shop = shop_store.get(conn, shop_id)
    return shop["name"] if shop else None


def _problem_label(row: dict[str, Any]) -> str:
    """原标题去掉店名的问题部分；临近超时去掉数量（恢复时已为 0）。"""
    if row["kind"] == "ship_deadline":
        return _DEADLINE_LABEL
    return title_for(row["kind"], shop_name=None, count=row["count"], detail=row["body"])


class NotificationService:
    def __init__(
        self, engine: Engine, events: EventBus, clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._engine = engine
        self._events = events
        self._clock = clock

    def _now(self) -> str:
        return _fmt(self._clock())

    def _publish(self, action: str, item: dict[str, Any] | None, *, alert: bool) -> None:
        self._events.publish(NOTIFICATION, {"action": action, "item": item, "alert": alert})

    # ---- 事件类 ----

    def emit(
        self, kind: Kind, *, shop_id: int | None, count: int = 1, detail: str | None = None,
    ) -> int:
        return self._emit(kind, shop_id=shop_id, count=count, detail=detail)

    def _emit(
        self, kind: Kind, *, shop_id: int | None, count: int, detail: str | None,
    ) -> int:
        with self._engine.begin() as conn:
            nid, action, alert = self._write_event(
                conn, kind, shop_id=shop_id, count=count, detail=detail)
            item = notification_store.get(conn, nid)
        self._publish(action, item, alert=alert)
        return nid

    def _write_event(
        self, conn: sa.Connection, kind: Kind, *, shop_id: int | None, count: int,
        detail: str | None, link: str | None = None,
    ) -> tuple[int, str, bool]:
        now = self._now()
        name = _shop_name(conn, shop_id)
        link = link or link_for(kind, shop_id, sync_type=detail)
        prev = None
        if shop_id is not None and kind not in _NO_MERGE:
            prev = notification_store.latest_unread_event(
                conn, shop_id, kind, link=link if kind in _MERGE_BY_LINK else None)
        if prev is not None:
            total = prev["count"] + count
            notification_store.update(
                conn, prev["id"], now, count=total,
                title=title_for(kind, shop_name=name, count=total, detail=detail),
            )
            return prev["id"], "updated", False
        nid = notification_store.insert(
            conn, kind=kind, level=LEVEL_BY_KIND[kind], shop_id=shop_id,
            title=title_for(kind, shop_name=name, count=count, detail=detail),
            link=link, count=count, created_at=now, updated_at=now,
        )
        return nid, "created", True

    # ---- 状态类 ----

    def raise_state(
        self, family: KindFamily, kind: Kind, *, shop_id: int, count: int = 1,
        detail: str | None = None,
    ) -> None:
        key = state_key(family, shop_id)
        now = self._now()
        with self._engine.begin() as conn:
            name = _shop_name(conn, shop_id)
            row = notification_store.open_state(conn, key)
            fields: dict[str, Any] = {"body": detail, "count": count}
            if row is None:
                last = notification_store.last_resolved_state(conn, key)
                if last is not None and (
                    _parse(now) - _parse(last["resolved_at"]) <= REOPEN_SILENT_WITHIN
                ):
                    row, fields["resolved_at"] = last, None
            if row is not None:
                fields.update(
                    kind=kind, level=LEVEL_BY_KIND[kind], link=link_for(kind, shop_id),
                    title=title_for(kind, shop_name=name, count=count, detail=detail),
                )
                notification_store.update(conn, row["id"], now, **fields)
                nid, action, alert = row["id"], "updated", False
            else:
                nid = notification_store.insert(
                    conn, kind=kind, level=LEVEL_BY_KIND[kind], shop_id=shop_id,
                    title=title_for(kind, shop_name=name, count=count, detail=detail),
                    body=detail, link=link_for(kind, shop_id), count=count,
                    state_key=key, created_at=now, updated_at=now,
                )
                action, alert = "created", True
            item = notification_store.get(conn, nid)
        self._publish(action, item, alert=alert)

    def resolve_state(self, family: KindFamily, *, shop_id: int) -> None:
        key = state_key(family, shop_id)
        now = self._now()
        recovered = None
        with self._engine.begin() as conn:
            row = notification_store.open_state(conn, key)
            if row is None:
                return
            fields: dict[str, Any] = {"resolved_at": now}
            if row["recovered_notified_at"] is None:
                rid, action, alert = self._write_event(
                    conn, "recovered", shop_id=shop_id, count=1,
                    detail=_problem_label(row), link=row["link"])
                fields["recovered_notified_at"] = now
                recovered = (action, notification_store.get(conn, rid), alert)
            notification_store.update(conn, row["id"], now, **fields)
            item = notification_store.get(conn, row["id"])
        self._publish("resolved", item, alert=False)
        if recovered is not None:
            action, rec_item, alert = recovered
            self._publish(action, rec_item, alert=alert)

    # ---- 查询与已读 ----

    def summary(self) -> dict[str, Any]:
        with self._engine.connect() as conn:
            unread = notification_store.unread_count(conn)
            groups: dict[int, dict[str, Any]] = {}
            for row in notification_store.open_strong_states(conn):
                sid = row["shop_id"]
                group = groups.get(sid)
                if group is None:
                    group = groups[sid] = {
                        "shop_id": sid, "shop_name": _shop_name(conn, sid) or "",
                        "kinds": [], "link": row["link"],
                    }
                if row["kind"] not in group["kinds"]:
                    group["kinds"].append(row["kind"])
        return {"unread": unread, "strong_open": [*groups.values()]}

    def mark_read(self, notification_id: int) -> bool:
        with self._engine.begin() as conn:
            notification_store.mark_read(conn, notification_id, self._now())
            item = notification_store.get(conn, notification_id)
        if item is None:
            return False
        self._publish("read", item, alert=False)
        return True

    def mark_all_read(self) -> None:
        with self._engine.begin() as conn:
            notification_store.mark_all_read(conn, self._now())
        self._publish("read", None, alert=False)

    def purge(self, now: datetime) -> int:
        """删除已读超过 30 天的记录；未解决的强状态由存储层保留。"""
        with self._engine.begin() as conn:
            return notification_store.purge_read_events_before(
                conn, _fmt(now - READ_RETENTION))

    def list(self, *, unread_only: bool, page: int, page_size: int = 50) -> dict[str, Any]:  # noqa: A003
        page = max(page, 1)
        page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
        with self._engine.connect() as conn:
            items, total = notification_store.list_page(
                conn, unread_only=unread_only, offset=(page - 1) * page_size, limit=page_size)
        return {"items": items, "total": total, "page": page, "page_size": page_size}
