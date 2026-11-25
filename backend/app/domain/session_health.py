"""会话健康度（按过期时间判断，纯函数）。"""

from datetime import datetime, timedelta
from typing import Literal

Health = Literal["healthy", "expiring", "expired"]

EXPIRING_WITHIN = timedelta(days=7)
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def health_from_expiry(expires_at: str | None, now: datetime) -> Health:
    """剩余 ≤ 7 天为 expiring，已到期为 expired。未知过期时间按 expired 处理（要求重新登录）。"""
    if not expires_at:
        return "expired"
    remaining = datetime.strptime(expires_at, _ISO_FMT).replace(tzinfo=now.tzinfo) - now
    if remaining <= timedelta(0):
        return "expired"
    if remaining <= EXPIRING_WITHIN:
        return "expiring"
    return "healthy"
