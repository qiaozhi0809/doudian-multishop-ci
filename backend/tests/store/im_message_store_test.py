from app.store import im_message_store, shop_store
from tests.store.conftest import LATER, NOW

CONV = "conv-test-1"


def _shop(conn, name="测试店A"):
    return shop_store.create(conn, name, NOW)


def _msg(message_id="msg-test-1", *, conv=CONV, sent_at=NOW, role="buyer", text="在吗"):
    return {
        "conversation_id": conv, "message_id": message_id, "sender_role": role,
        "text": text, "sent_at": sent_at,
    }


def _ids(rows):
    return [r["message_id"] for r in rows]


def test_insert_ignore_dedupes_per_shop(engine):
    with engine.begin() as conn:
        a, b = _shop(conn), _shop(conn, "测试店B")
        assert im_message_store.insert_ignore(conn, a, [_msg()], NOW) == 1
        assert im_message_store.insert_ignore(conn, a, [_msg(text="改过的正文")], LATER) == 0
        assert im_message_store.insert_ignore(conn, b, [_msg()], NOW) == 1
        [row] = im_message_store.list_for_conversation(conn, a, CONV)
        assert row["text"] == "在吗" and row["captured_at"] == NOW  # 重复帧不覆盖首次记录
        assert row["shop_id"] == a and row["sender_role"] == "buyer" and row["sent_at"] == NOW


def test_insert_ignore_counts_only_new_rows(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        im_message_store.insert_ignore(conn, sid, [_msg()], NOW)
        batch = [_msg(), _msg("msg-test-2"), _msg("msg-test-2")]
        assert im_message_store.insert_ignore(conn, sid, batch, NOW) == 1


def test_insert_ignore_handles_empty_and_large_batches(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        assert im_message_store.insert_ignore(conn, sid, [], NOW) == 0
        batch = [_msg(f"msg-test-{i}") for i in range(1200)]
        assert im_message_store.insert_ignore(conn, sid, batch, NOW) == 1200


def test_list_for_conversation_ordered_and_limited(engine):
    with engine.begin() as conn:
        a, b = _shop(conn), _shop(conn, "测试店B")
        im_message_store.insert_ignore(conn, a, [
            _msg("msg-test-3", sent_at="2026-11-25T00:03:00Z"),
            _msg("msg-test-1", sent_at="2026-11-25T00:01:00Z"),
            _msg("msg-test-2", sent_at="2026-11-25T00:02:00Z"),
            _msg("msg-test-other", conv="conv-test-2"),
        ], NOW)
        im_message_store.insert_ignore(conn, b, [_msg("msg-test-b")], NOW)
        rows = im_message_store.list_for_conversation(conn, a, CONV)
        assert _ids(rows) == ["msg-test-1", "msg-test-2", "msg-test-3"]
        latest = im_message_store.list_for_conversation(conn, a, CONV, limit=2)
        assert _ids(latest) == ["msg-test-2", "msg-test-3"]


def test_list_for_conversation_default_limit_is_200(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        batch = [
            _msg(f"msg-test-{i}", sent_at=f"2026-11-25T00:{i // 60:02d}:{i % 60:02d}Z")
            for i in range(201)
        ]
        im_message_store.insert_ignore(conn, sid, batch, NOW)
        rows = im_message_store.list_for_conversation(conn, sid, CONV)
        assert len(rows) == 200 and rows[0]["message_id"] == "msg-test-1"


def test_recent_for_shop_since(engine):
    with engine.begin() as conn:
        a, b = _shop(conn), _shop(conn, "测试店B")
        im_message_store.insert_ignore(conn, a, [
            _msg("msg-test-new", conv="conv-test-2", sent_at="2026-11-25T00:03:00Z"),
            _msg("msg-test-old", sent_at="2026-11-24T23:59:59Z"),
            _msg("msg-test-edge", sent_at=NOW),
        ], LATER)  # 抓取时间都晚于 since：过滤看的是发送时间
        im_message_store.insert_ignore(conn, b, [_msg("msg-test-b", sent_at=LATER)], LATER)
        rows = im_message_store.recent_for_shop(conn, a, NOW)
        assert _ids(rows) == ["msg-test-edge", "msg-test-new"]


def test_purge_before_uses_captured_at(engine):
    with engine.begin() as conn:
        sid = _shop(conn)
        cutoff = "2026-10-26T00:00:00Z"
        im_message_store.insert_ignore(
            conn, sid, [_msg("msg-test-old", sent_at=LATER)], "2026-10-25T23:59:59Z")
        im_message_store.insert_ignore(
            conn, sid, [_msg("msg-test-edge", sent_at="2026-10-01T00:00:00Z")], cutoff)
        assert im_message_store.purge_before(conn, cutoff) == 1
        assert _ids(im_message_store.list_for_conversation(conn, sid, CONV)) == ["msg-test-edge"]
