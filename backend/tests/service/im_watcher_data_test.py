"""飞鸽常驻页的数据：打开期间的回调不丢、历史基线、消息存库、审计。"""

from datetime import timedelta

import pytest
from structlog.testing import capture_logs

from app.adapter.flybird.parse import ConvListResult
from app.store import im_message_store
from tests.service.im_session_test import msg
from tests.service.im_watcher_support import ADMIN, Rig, drain, until


@pytest.fixture
async def rig(engine, tmp_path):
    rig = Rig(engine, tmp_path)
    yield rig
    await rig.watcher.shutdown()


# ---- 缓冲 ----


async def test_callbacks_during_attach_are_replayed_to_session(rig):
    def early(page) -> None:
        page.on_frame(b"\x00")
        page.on_list(ConvListResult(0, {"1001": "conv-test-1"}))
        page.on_messages([msg("msg-test-1")])

    rig.attach.during = early
    await rig.start()

    await until(lambda: rig.messages())
    view = rig.watcher.snapshot(rig.shop_id)[0]
    assert (view.conversation_id, view.key, view.pending) == ("1001", "conv-test-1", 1)

    rig.attach.pages[0].on_messages([msg("msg-test-2", at=1)])  # 之后直接转发
    await until(lambda: len(rig.messages()) == 2)


async def test_version_low_seen_during_attach_is_not_lost(rig):
    rig.attach.during = lambda page: page.on_list(ConvListResult(11001, {}))

    await rig.watcher.start(rig.shop_id, actor=ADMIN)

    await until(lambda: rig.attach.pages and rig.attach.pages[0].reloads == 1)


# ---- 消息与审计 ----


async def test_messages_persisted_and_text_not_logged(rig):
    with capture_logs() as logs:
        await rig.start()
        rig.attach.pages[0].on_messages([msg("msg-test-1")])
        await until(lambda: rig.messages())
        await rig.watcher.stop(rig.shop_id, reason="ineligible", actor=ADMIN)

    row = rig.messages()[0]
    assert (row["message_id"], row["text"], row["sender_role"]) == ("msg-test-1", "在吗", "buyer")
    assert row["captured_at"] == "2026-12-01T02:00:00Z"
    assert "在吗" not in str(logs)
    assert "在吗" not in str(rig.published)


async def test_save_failure_logs_count_only_and_keeps_running(rig, monkeypatch):
    def boom(*_args):
        raise RuntimeError("写库失败：在吗")

    await rig.start()
    monkeypatch.setattr(im_message_store, "insert_ignore", boom)
    with capture_logs() as logs:
        rig.attach.pages[0].on_messages([msg("msg-test-1"), msg("msg-test-2")])
        await until(lambda: any(e["event"] == "im.save_failed" for e in logs))
        await drain()

    failed = next(e for e in logs if e["event"] == "im.save_failed")
    assert (failed["shop_id"], failed["count"]) == (rig.shop_id, 2)
    assert "在吗" not in str(logs)
    assert rig.state() == "running"


async def test_history_is_loaded_as_baseline(rig):
    sent = rig.now - timedelta(hours=2)
    with rig.engine.begin() as conn:
        im_message_store.insert_ignore(conn, rig.shop_id, [{
            "conversation_id": "1001", "message_id": "msg-test-0", "sender_role": "buyer",
            "text": "在吗", "sent_at": sent.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, {
            "conversation_id": "1002", "message_id": "msg-test-old", "sender_role": "buyer",
            "text": "在吗", "sent_at": "2026-11-01T00:00:00Z",
        }], "2026-12-01T00:00:00Z")

    await rig.start()

    assert [v.conversation_id for v in rig.watcher.snapshot(rig.shop_id)] == ["1001"]
    assert ("im_unread_changed", {"shop_id": rig.shop_id, "unread": 1, "new": 0}) in rig.published


async def test_audit_on_start_and_stop(rig, monkeypatch):
    blocked = [5]
    monkeypatch.setattr("app.adapter.flybird.read_guard.blocked_count", lambda: blocked[0])
    await rig.start()
    rig.attach.pages[0].on_messages([msg("msg-test-1")])
    await until(lambda: rig.messages())
    blocked[0] = 8

    await rig.watcher.stop(rig.shop_id, reason="ineligible", actor=ADMIN)

    start, stop = rig.audits("im.start"), rig.audits("im.stop")
    assert [(r["shop_id"], r["actor"], r["result"]) for r in start] == [(rig.shop_id, ADMIN, "ok")]
    assert [(r["actor"], r["result"]) for r in stop] == [(ADMIN, "ok")]
    assert stop[0]["resp"] == {"reason": "ineligible", "read_blocked": 3}
    assert "在吗" not in str(start + stop)


async def test_audit_start_failure(rig):
    rig.attach.error = TimeoutError("goto")

    await rig.start(wait="backoff")

    assert [r["result"] for r in rig.audits("im.start")] == ["error"]
    assert rig.audits("im.start")[0]["resp"]["reason"] == "error"
    assert rig.audits("im.stop") == []


async def test_attach_failure_closes_context_and_backs_off(rig):
    rig.attach.error = TimeoutError("goto")

    await rig.start(wait="backoff")

    assert rig.registry.opened[0].context.closed
    assert rig.registry.list() == []
    assert rig.watcher.status(rig.shop_id).last_error == "TimeoutError"
    assert rig.time.slept == [60]
