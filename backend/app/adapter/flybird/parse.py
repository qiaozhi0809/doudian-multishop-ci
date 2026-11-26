"""飞鸽解析（纯函数，只解码）：会话列表 JSON 与长连接下行帧（docs/api/flybird.md §2、§3）。

解析不了的输入一律返回空结果，不抛异常。
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlsplit

from app.adapter.flybird import endpoints as ep
from app.shared.time_bj import parse_platform_time

SenderRole = Literal["buyer", "agent", "robot", "platform"]

_PLATFORM: SenderRole = "platform"
_NO_CODE = -1  # 响应里没有可用的 code：按失败处理

# protobuf wire type
_VARINT = 0
_FIXED64 = 1
_LENGTH = 2
_FIXED32 = 5
_FIXED_SIZES = {_FIXED64: 8, _FIXED32: 4}
_VARINT_MAX_BYTES = 10

_Fields = dict[int, int | bytes]


@dataclass(frozen=True)
class ConvListResult:
    code: int
    keys: dict[str, str]  # 会话 short ID → 会话键


@dataclass(frozen=True)
class Message:
    conversation_id: str
    message_id: str
    sender_role: SenderRole
    text: str = field(repr=False)  # 正文不进日志
    sent_at: str


class _Malformed(ValueError):
    """帧结构不符合预期。"""


# ---- 会话列表 ----


def is_conv_list_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.hostname == ep.CONV_LIST_HOST and parts.path == ep.CONV_LIST_PATH


def _json_id(value: object) -> str:
    return str(value) if isinstance(value, str | int) and value else ""


def parse_conv_list(payload: dict) -> ConvListResult:
    body = payload if isinstance(payload, dict) else {}
    code = body.get("code")
    if not isinstance(code, int):
        code = _NO_CODE
    items = body.get("data")
    if code != ep.CONV_LIST_OK or not isinstance(items, list):
        return ConvListResult(code, {})
    keys: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = _json_id(item.get(ep.CONV_FIELDS["key"]))
        short_id = _json_id(item.get(ep.CONV_FIELDS["short_id"]))
        if key and short_id:
            keys[short_id] = key
    return ConvListResult(code, keys)


# ---- protobuf 读取 ----


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    for index, byte in enumerate(data[pos : pos + _VARINT_MAX_BYTES]):
        value |= (byte & 0x7F) << (7 * index)
        if byte < 0x80:
            return value, pos + index + 1
    raise _Malformed("varint 不完整")


def _fields(data: bytes) -> Iterator[tuple[int, int | bytes]]:
    """逐个交出 varint 与 length-delimited 字段；定长字段本协议用不到，跳过。"""
    pos = 0
    while pos < len(data):
        tag, pos = _read_varint(data, pos)
        number, wire = tag >> 3, tag & 0x07
        if number == 0:
            raise _Malformed("字段号为 0")
        if wire == _VARINT:
            value, pos = _read_varint(data, pos)
            yield number, value
            continue
        if wire == _LENGTH:
            size, pos = _read_varint(data, pos)
        elif wire in _FIXED_SIZES:
            size = _FIXED_SIZES[wire]
        else:
            raise _Malformed("未知 wire type")
        if size > len(data) - pos:
            raise _Malformed("长度越界")
        if wire == _LENGTH:
            yield number, data[pos : pos + size]
        pos += size


def _submessage(fields: _Fields, number: int) -> bytes:
    value = fields.get(number)
    if not isinstance(value, bytes):
        raise _Malformed(f"缺少字段 {number}")
    return value


def _payload(raw: bytes) -> _Fields:
    """外层帧里 pb 格式的 payload。"""
    frame = dict(_fields(raw))
    if frame.get(ep.FRAME_PAYLOAD_TYPE) != ep.PAYLOAD_TYPE_PB:
        raise _Malformed("payload 不是 pb")
    return dict(_fields(_submessage(frame, ep.FRAME_PAYLOAD)))


# ---- 帧 ----


def frame_cmd(raw: bytes) -> int | None:
    try:
        cmd = _payload(raw).get(ep.PAYLOAD_CMD)
    except _Malformed:
        return None
    return cmd if isinstance(cmd, int) else None


def is_new_message_frame(raw: bytes) -> bool:
    return frame_cmd(raw) in ep.NEW_MESSAGE_CMDS


def _text(value: int | bytes | None) -> str | None:
    if not isinstance(value, bytes):
        return None
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _wire_id(value: int | bytes | None) -> str | None:
    """编号字段：实测记录未写明 wire type，数字与字符串都接受。"""
    if isinstance(value, int):
        return str(value) if value else None
    return _text(value) or None


def _sent_at(value: int | bytes | None) -> str | None:
    if not isinstance(value, int):
        return None
    try:
        return parse_platform_time(value // 1000)
    except (ValueError, OverflowError, OSError):
        return None


def _message(data: bytes) -> Message | None:
    """单条消息体；不是聊天消息或缺字段返回 None。"""
    fields: _Fields = {}
    role = _PLATFORM
    for number, value in _fields(data):
        if number != ep.MSG_FIELDS["ext"]:
            fields[number] = value
        elif isinstance(value, bytes):
            pair = dict(_fields(value))
            if _text(pair.get(ep.EXT_KEY)) == ep.ROLE_EXT_KEY:
                role = ep.ROLE_BY_VALUE.get(_text(pair.get(ep.EXT_VALUE)), _PLATFORM)
    if fields.get(ep.MSG_FIELDS["type"]) != ep.CHAT_MSG_TYPE:
        return None
    conversation_id = _wire_id(fields.get(ep.MSG_FIELDS["conversation_id"]))
    message_id = _wire_id(fields.get(ep.MSG_FIELDS["message_id"]))
    text = _text(fields.get(ep.MSG_FIELDS["text"]))
    sent_at = _sent_at(fields.get(ep.MSG_FIELDS["sent_at_ms"]))
    if conversation_id is None or message_id is None or text is None or sent_at is None:
        return None
    return Message(conversation_id, message_id, role, text, sent_at)


def parse_message_frame(raw: bytes) -> list[Message]:
    try:
        payload = _payload(raw)
        if payload.get(ep.PAYLOAD_CMD) != ep.CMD_MESSAGE:
            return []
        push = dict(_fields(_submessage(payload, ep.PAYLOAD_PUSH)))
        messages = [
            _message(value)
            for number, value in _fields(_submessage(push, ep.CMD_MESSAGE))
            if number == ep.PUSH_MESSAGE and isinstance(value, bytes)
        ]
    except _Malformed:
        return []
    return [message for message in messages if message is not None]
