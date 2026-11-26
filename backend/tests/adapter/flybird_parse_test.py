"""飞鸽解析（纯函数）：会话列表与 WebSocket 帧（docs/api/flybird.md §2、§3），数据全部虚构。

下面的拼帧小工具照 flybird.md §3 的字段号手写，故意不引用 app 常量：常量写错时测试要能发现。
"""

import json
from pathlib import Path

import pytest

from app.adapter.flybird.parse import (
    Message,
    frame_cmd,
    is_conv_list_url,
    is_msg_pull_url,
    is_new_message_frame,
    parse_conv_list,
    parse_message_frame,
    parse_message_pull,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "flybird"
LIST_PATH = "/chat/api/backstage/conversation/get_current_conversation_list"
SENT_MS = 1795658400123
SENT_ISO = "2026-11-26T02:00:00Z"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append(value & 0x7F | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def pb(number: int, value: int | str | bytes) -> bytes:
    """一个字段：int → varint，str / bytes → length-delimited。"""
    if isinstance(value, int):
        return varint(number << 3) + varint(value)
    data = value.encode() if isinstance(value, str) else value
    return varint(number << 3 | 2) + varint(len(data)) + data


def outer_frame(payload: bytes, *, kind: str = "pb", service: int = 10001, method: int = 1):
    return b"".join([
        pb(1, 7), pb(2, SENT_MS), pb(3, service), pb(4, method),
        pb(5, pb(1, "k") + pb(2, "v")), pb(7, kind), pb(8, payload),
    ])


def cmd_frame(cmd: int) -> bytes:
    return outer_frame(pb(1, cmd))


def message_body(
    *,
    message_id: int | str | None = "msg-test-1",
    conversation: int | str | None = 1001,
    msg_type: int | None = 1000,
    text: str | bytes | None = "在吗",
    role: str | None = "1",
    sent_ms: int | None = SENT_MS,
    uname: str | bytes | None = None,
) -> bytes:
    """cmd 500 消息体；传 None 表示不带该字段。"""
    fields = [(3, message_id), (5, conversation), (6, msg_type), (8, text), (10, sent_ms)]
    body = b"".join(pb(number, value) for number, value in fields if value is not None)
    body += pb(9, pb(1, "other_key") + pb(2, "x"))
    if role is not None:
        body += pb(9, pb(1, "sender_role") + pb(2, role))
    if uname is not None:
        body += pb(9, pb(1, "uname") + pb(2, uname))
    return body


def message_frame(*bodies: bytes, cmd: int = 500) -> bytes:
    push = pb(500, b"".join(pb(5, body) for body in bodies))
    return outer_frame(pb(1, cmd) + pb(6, push))


# ---- 会话列表 ----


def test_conv_list_url_requires_pigeon_host():
    assert is_conv_list_url(f"https://pigeon.jinritemai.com{LIST_PATH}?biz_type=4&pageNo=0")
    assert not is_conv_list_url(f"https://im.jinritemai.com{LIST_PATH}?biz_type=4")
    assert not is_conv_list_url(f"https://pigeon.jinritemai.com.example.test{LIST_PATH}")


def test_conv_list_url_requires_list_path():
    assert not is_conv_list_url("https://pigeon.jinritemai.com/backstage/currentuser")


def test_parse_conv_list_ok():
    result = parse_conv_list(load("conv_list_ok.json"))
    assert result.code == 0
    assert result.keys == {"1001": "conv-test-1"}


def test_parse_conv_list_version_too_low():
    result = parse_conv_list(load("conv_list_11001.json"))
    assert result.code == 11001
    assert result.keys == {}


def test_parse_conv_list_numeric_short_id_and_incomplete_items():
    result = parse_conv_list({"code": 0, "data": [
        {"subConversationId": "conv-test-1", "parentConShortId": 1001},
        {"subConversationId": "conv-test-2"},
        {"parentConShortId": "1003"},
        {"subConversationId": "", "parentConShortId": "1004"},
        "不是对象",
    ]})
    assert result.keys == {"1001": "conv-test-1"}


@pytest.mark.parametrize("payload", [{}, {"code": 0}, {"code": 0, "data": None}, []])
def test_parse_conv_list_unexpected_shape_never_raises(payload):
    assert parse_conv_list(payload).keys == {}


def test_parse_conv_list_missing_code_is_not_success():
    assert parse_conv_list({"data": []}).code != 0


# ---- 帧识别 ----


def test_frame_cmd_reads_payload_field1():
    assert frame_cmd(cmd_frame(500)) == 500


@pytest.mark.parametrize("raw", [
    b"",
    b"\xff\xff",
    b"hi",
    b"\x42\x05\x08",  # payload 声明长度超过实际
    b"\x08" + b"\xff" * 11,  # varint 超过 10 字节
])
def test_frame_cmd_garbage_returns_none(raw):
    assert frame_cmd(raw) is None


def test_frame_cmd_json_platform_reminder_returns_none():
    payload = json.dumps({"data": {"attention_time": 60}}).encode()
    raw = outer_frame(payload, kind="json", service=1, method=5)
    assert frame_cmd(raw) is None


def test_frame_cmd_non_pb_payload_returns_none():
    assert frame_cmd(outer_frame(pb(1, 500), kind="json")) is None


def test_new_message_frame_500_and_504():
    assert is_new_message_frame(cmd_frame(500))
    assert is_new_message_frame(cmd_frame(504))


def test_heartbeat_16001_not_new_message():
    assert not is_new_message_frame(cmd_frame(16001))
    assert not is_new_message_frame(b"\xff\xff")


# ---- 消息 ----


def test_parse_message_frame_buyer_text():
    assert parse_message_frame(message_frame(message_body())) == [
        Message("1001", "msg-test-1", "buyer", "在吗", SENT_ISO)
    ]


def test_parse_message_frame_numeric_message_id():
    [message] = parse_message_frame(message_frame(message_body(message_id=2**62)))
    assert message.message_id == str(2**62)


def test_parse_message_frame_skips_unknown_wire_types():
    fixed64 = varint(20 << 3 | 1) + bytes(8)
    fixed32 = varint(21 << 3 | 5) + bytes(4)
    body = fixed64 + message_body() + fixed32 + pb(7, 42)
    assert [m.text for m in parse_message_frame(message_frame(body))] == ["在吗"]


@pytest.mark.parametrize(("role", "expected"), [
    ("1", "buyer"), ("2", "agent"), ("4", "robot"), (None, "platform"), ("9", "platform"),
])
def test_parse_message_frame_roles(role, expected):
    [message] = parse_message_frame(message_frame(message_body(role=role)))
    assert message.sender_role == expected


@pytest.mark.parametrize("msg_type", [50001, 50002])
def test_parse_message_frame_system_types_dropped(msg_type):
    assert parse_message_frame(message_frame(message_body(msg_type=msg_type))) == []


def test_parse_message_frame_keeps_only_chat_messages_in_order():
    raw = message_frame(
        message_body(message_id="msg-test-1"),
        message_body(message_id="msg-test-2", msg_type=50001),
        message_body(message_id="msg-test-3", role="2"),
    )
    assert [m.message_id for m in parse_message_frame(raw)] == ["msg-test-1", "msg-test-3"]


@pytest.mark.parametrize(
    "missing", ["message_id", "conversation", "msg_type", "text", "sent_ms"]
)
def test_parse_message_frame_missing_field_returns_empty(missing):
    assert parse_message_frame(message_frame(message_body(**{missing: None}))) == []


@pytest.mark.parametrize("override", [{"text": b"\xff\xfe"}, {"sent_ms": 2**62}])
def test_parse_message_frame_bad_value_returns_empty(override):
    assert parse_message_frame(message_frame(message_body(**override))) == []


def test_parse_message_frame_other_cmd_returns_empty():
    assert parse_message_frame(message_frame(message_body(), cmd=504)) == []
    assert parse_message_frame(cmd_frame(500)) == []


def test_parse_message_frame_truncated_returns_empty():
    raw = message_frame(message_body())
    for end in range(len(raw)):
        assert parse_message_frame(raw[:end]) == [], end


def test_message_repr_hides_text():
    [message] = parse_message_frame(message_frame(message_body()))
    assert "在吗" not in repr(message)
    assert "在吗" not in str(message)
    assert "msg-test-1" in repr(message)


# ---- 买家昵称（扩展键 uname） ----


def test_buyer_name_from_uname_for_buyer_only():
    raw = message_frame(
        message_body(message_id="msg-test-1", uname="测试买家"),
        message_body(message_id="msg-test-2", uname="测试客服", role="2"),
        message_body(message_id="msg-test-3", uname="测试机器人", role="4"),
        message_body(message_id="msg-test-4", uname="测试平台", role=None),
    )
    assert [m.buyer_name for m in parse_message_frame(raw)] == ["测试买家", None, None, None]


def test_buyer_name_independent_of_ext_order():
    body = message_body(role=None, uname="测试买家") + pb(9, pb(1, "sender_role") + pb(2, "1"))
    [message] = parse_message_frame(message_frame(body))
    assert message.buyer_name == "测试买家"


@pytest.mark.parametrize("uname", [None, "", b"\xff\xfe"])
def test_buyer_name_missing_or_unreadable_keeps_message(uname):
    [message] = parse_message_frame(message_frame(message_body(uname=uname)))
    assert (message.text, message.buyer_name) == ("在吗", None)


def test_buyer_name_hidden_in_repr():
    [message] = parse_message_frame(message_frame(message_body(uname="测试买家")))
    assert message.buyer_name == "测试买家"
    assert "测试买家" not in repr(message)
    assert "测试买家" not in str(message)


# ---- 增量拉取响应（get_user_message） ----

PULL_PATH = "/pigeon_im/v3/message/get_user_message"


def pull_body(*conversations: list[bytes], extra: list[bytes] = (), cmd: int = 12048) -> bytes:
    """响应体：{1: cmd, 6: {cmd: {1: [{1: 游标, 2: {1: 会话, 2: 消息...}}], 2: {1: 消息...}}}}。"""
    items = b"".join(
        pb(1, pb(1, 99) + pb(2, pb(1, 1001) + b"".join(pb(2, body) for body in bodies)))
        for bodies in conversations
    )
    if extra:
        items += pb(2, b"".join(pb(1, body) for body in extra))
    return pb(1, cmd) + pb(2, 10068) + pb(6, pb(cmd, items))


def test_msg_pull_url_requires_fxg_host_and_path():
    assert is_msg_pull_url(f"https://fxg.jinritemai.com{PULL_PATH}?PIGEON_BIZ_TYPE=2")
    assert not is_msg_pull_url(f"https://pigeon.jinritemai.com{PULL_PATH}")
    assert not is_msg_pull_url("https://fxg.jinritemai.com/pigeon_im/v1/message/get_by_conversation")


def test_parse_message_pull_buyer_messages_across_conversations():
    body = pull_body(
        [message_body(), message_body(message_id="msg-test-2", text="还在吗")],
        [message_body(message_id="msg-test-3", conversation=1002, role="2", text="在的")],
    )
    got = parse_message_pull(body)
    assert [(m.conversation_id, m.message_id, m.sender_role, m.text) for m in got] == [
        ("1001", "msg-test-1", "buyer", "在吗"),
        ("1001", "msg-test-2", "buyer", "还在吗"),
        ("1002", "msg-test-3", "agent", "在的"),
    ]
    assert got[0].sent_at == SENT_ISO


def test_parse_message_pull_carries_buyer_name():
    [message] = parse_message_pull(pull_body([message_body(uname="测试买家")]))
    assert message.buyer_name == "测试买家"


def test_parse_message_pull_drops_system_types_in_extra_group():
    body = pull_body([message_body()], extra=[message_body(message_id="cmd-1", msg_type=50002)])
    assert [m.message_id for m in parse_message_pull(body)] == ["msg-test-1"]


def test_parse_message_pull_empty_result():
    assert parse_message_pull(pb(1, 12048) + pb(6, pb(12048, b""))) == []


@pytest.mark.parametrize(
    "body", [b"", b"\xff\xff", pb(1, 500), pull_body([message_body()], cmd=500)]
)
def test_parse_message_pull_bad_or_other_body_returns_empty(body):
    assert parse_message_pull(body) == []
