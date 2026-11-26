"""每日清理：备份之后删除超过 30 天的飞鸽消息；清理失败不算备份失败。数据全部虚构。"""

import asyncio
from datetime import timedelta

from structlog.testing import capture_logs

from app.main import _daily_backup
from app.store import im_message_store

ISO = "%Y-%m-%dT%H:%M:%SZ"


def save(api, shop_id: int, message_id: str, captured_at: str) -> None:
    with api.app.state.engine.begin() as conn:
        im_message_store.insert_ignore(conn, shop_id, [{
            "conversation_id": "1001", "message_id": message_id, "sender_role": "buyer",
            "text": "在吗", "sent_at": captured_at,
        }], captured_at)


def message_ids(api, shop_id: int) -> list[str]:
    with api.app.state.engine.connect() as conn:
        return [m["message_id"] for m in im_message_store.recent_for_shop(conn, shop_id, "")]


def test_daily_job_purges_im_messages_after_backup(api, clock, monkeypatch):
    shop_id = api.new_shop(ip_n=None)
    save(api, shop_id, "msg-test-old", (clock() - timedelta(days=31)).strftime(ISO))
    save(api, shop_id, "msg-test-kept", (clock() - timedelta(days=29)).strftime(ISO))
    order: list[str] = []
    create, purge = api.app.state.backup.create, api.app.state.im.purge_messages
    monkeypatch.setattr(api.app.state.backup, "create",
                        lambda *a: (order.append("backup"), create(*a))[1])
    monkeypatch.setattr(api.app.state.im, "purge_messages",
                        lambda now: (order.append("purge"), purge(now))[1])

    with capture_logs() as logs:
        asyncio.run(_daily_backup(api.app)())

    assert order == ["backup", "purge"]
    assert message_ids(api, shop_id) == ["msg-test-kept"]
    purged = next(e for e in logs if e["event"] == "im.messages_purged")
    assert purged["count"] == 1
    assert "在吗" not in str(logs)


def test_im_purge_failure_does_not_fail_backup(api, monkeypatch):
    def boom(_now):
        raise RuntimeError("purge failed")

    monkeypatch.setattr(api.app.state.im, "purge_messages", boom)

    with capture_logs() as logs:
        result = asyncio.run(_daily_backup(api.app)())

    assert result["trigger"] == "daily"
    assert any(e["event"] == "im.messages_purge_failed" for e in logs)
