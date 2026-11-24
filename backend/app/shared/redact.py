"""脱敏：日志与审计一律经 redact_mapping（engineering-rules 8.1）。"""

import re
from typing import Any

_FULL_MASK = "***"
_ALWAYS_SECRET_KEYS = ("cookie", "token", "password")
# 以 _display / _id 结尾的键（proxy_display、address_id）是给排查用的，不按下列规则打码
_CONTEXT_SECRET_KEYS = ("proxy", "address", "detail")
_SAFE_SUFFIXES = ("_display", "_id")
_PHONE_KEYS = ("mobile", "phone")
_NAME_KEYS = ("receiver", "user_name", "username", "buyer")
_PHONE_RE = re.compile(r"(?<!\d)(1[3-9]\d)\d{4}(\d{4})(?!\d)")


def _norm(key: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key).lower()


def mask_phone(value: str) -> str:
    s = str(value)
    if len(s) < 7:
        return _FULL_MASK
    return f"{s[:3]}****{s[-4:]}"


def mask_name(value: str) -> str:
    s = str(value)
    if not s:
        return s
    return s[0] + "*" * (len(s) - 1) if len(s) > 1 else "*"


def scrub_text(text: str) -> str:
    """字符串里夹带的手机号打码。"""
    return _PHONE_RE.sub(r"\1****\2", text)


def _redact_value(key: str, value: Any) -> Any:
    k = _norm(key)
    if any(s in k for s in _ALWAYS_SECRET_KEYS):
        return _FULL_MASK
    if any(s in k for s in _CONTEXT_SECRET_KEYS) and not k.endswith(_SAFE_SUFFIXES):
        return _FULL_MASK
    if any(s in k for s in _PHONE_KEYS) or "tel" in k.split("_"):
        return mask_phone(value) if isinstance(value, str) else _FULL_MASK
    if any(s in k for s in _NAME_KEYS):
        return mask_name(value) if isinstance(value, str) else _FULL_MASK
    return _redact_plain(value)


def _redact_plain(value: Any) -> Any:
    if isinstance(value, dict):
        return redact_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_redact_plain(v) for v in value]
    if isinstance(value, str):
        return scrub_text(value)
    return value


def redact_mapping(d: dict) -> dict:
    """递归脱敏，返回新字典，不修改入参。"""
    return {k: _redact_value(str(k), v) for k, v in d.items()}
