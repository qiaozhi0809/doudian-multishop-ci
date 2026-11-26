"""手工维护 / 抓取得到的店铺画像字段格式：接口、服务、抓取入库共用一套规则。

数字一律用 ``[0-9]``：Python 的 ``\\d`` 会匹配全角与其他 Unicode 数字。
卡号只存后四位，粘贴整串卡号会被拒绝，防止整串卡号明文入库。
"""

import re
from collections.abc import Mapping

from app.domain.errors import InvalidRequest

PROFILE_RULES: dict[str, tuple[re.Pattern[str] | None, int, str]] = {
    "platform_shop_id": (re.compile(r"[0-9]{1,20}"), 20, "店铺ID是 1 到 20 位数字"),
    "bank_name": (None, 50, "开户行不超过 50 个字"),
    "bank_tail": (re.compile(r"[0-9]{4}"), 4, "卡号尾号是 4 位数字"),
}


def validate_profile(key: str, value: str) -> str | None:
    """去首尾空白；空串 = 清空（None）；格式不符抛 InvalidRequest（消息可直接展示）。"""
    value = value.strip()
    if not value:
        return None
    pattern, max_len, message = PROFILE_RULES[key]
    if len(value) > max_len or (pattern is not None and not pattern.fullmatch(value)):
        raise InvalidRequest(message)
    return value


def clean_scraped(info: Mapping[str, str]) -> tuple[dict[str, str], list[str]]:
    """抓取结果按同一规则过滤：返回（合规字段, 被丢弃的字段名）。不在规则里的键原样保留。"""
    kept: dict[str, str] = {}
    dropped: list[str] = []
    for key, value in info.items():
        if key not in PROFILE_RULES:
            kept[key] = value
            continue
        try:
            valid = validate_profile(key, value)
        except InvalidRequest:
            dropped.append(key)
            continue
        if valid is not None:
            kept[key] = valid
    return kept, sorted(dropped)
