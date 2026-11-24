"""本机管理员登录的纯规则（backend 5.16）。"""

from datetime import datetime, timedelta

MIN_PASSWORD_LENGTH = 8
MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=5)
SESSION_IDLE_LIMIT = timedelta(hours=12)
SESSION_ABSOLUTE_LIMIT = timedelta(days=7)
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


def validate_password(password: str) -> list[str]:
    if len(password) < MIN_PASSWORD_LENGTH:
        return [f"密码至少 {MIN_PASSWORD_LENGTH} 位"]
    return []


def after_failure(failed_attempts: int, now: datetime) -> tuple[int, str | None]:
    """记一次失败：返回 (新的失败计数, 锁定到期时间)。达到上限即锁定并把计数清零。"""
    count = failed_attempts + 1
    if count >= MAX_FAILED_ATTEMPTS:
        return 0, (now + LOCK_DURATION).strftime(_ISO_FMT)
    return count, None


def session_alive(created_at: str, last_seen_at: str, now: datetime) -> bool:
    """空闲不超过 12 小时，且自创建起不超过 7 天。"""
    created = datetime.strptime(created_at, _ISO_FMT).replace(tzinfo=now.tzinfo)
    last_seen = datetime.strptime(last_seen_at, _ISO_FMT).replace(tzinfo=now.tzinfo)
    return now - last_seen <= SESSION_IDLE_LIMIT and now - created <= SESSION_ABSOLUTE_LIMIT
