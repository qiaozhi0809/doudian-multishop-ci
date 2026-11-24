"""平台时间字段 → UTC ISO；业务日期按北京时间。"""

import re
from datetime import UTC, datetime, timedelta, timezone

BEIJING = timezone(timedelta(hours=8))
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
_BJ_FMT = "%Y-%m-%d %H:%M:%S"


def parse_platform_time(value: int | str | None) -> str | None:
    """接受 unix 秒（数字或数字字符串）或「YYYY-MM-DD HH:MM:SS」北京时间；空值返回 None。"""
    if value is None or value == "" or value == 0:
        return None
    if isinstance(value, str):
        s = value.strip()
        if s == "":
            return None
        if re.fullmatch(r"\d+", s):
            value = int(s)
        else:
            try:
                dt = datetime.strptime(s, _BJ_FMT).replace(tzinfo=BEIJING)
            except ValueError as e:
                raise ValueError(f"无法解析平台时间: {value!r}") from e
            return dt.astimezone(UTC).strftime(_ISO_FMT)
    if value == 0:
        return None
    return datetime.fromtimestamp(value, UTC).strftime(_ISO_FMT)


def to_biz_date(iso_utc: str) -> str:
    dt = datetime.strptime(iso_utc, _ISO_FMT).replace(tzinfo=UTC)
    return dt.astimezone(BEIJING).strftime("%Y-%m-%d")
