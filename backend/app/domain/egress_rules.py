"""每店固定出口的纯规则（backend 5.17）。

代理 URL 校验、代理商格式解析、归一化（代理池去重键）、出口判定、到期状态。
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import quote, unquote, urlparse

from app.shared.time_bj import BEIJING

EgressVerdict = Literal["ok", "unreachable", "changed", "duplicate"]
ExpiryState = Literal["ok", "expiring", "expired"]

ALLOWED_PROXY_SCHEMES = ("http", "https")
EXPIRING_WITHIN = timedelta(days=7)
_PROVIDER_FIELDS = 5


def validate_proxy_url(url: str) -> list[str]:
    """返回错误列表（空表示合法）。错误信息不含账号密码。"""
    try:
        u = urlparse(url)
        port = u.port
    except ValueError:
        return ["代理地址格式不正确"]
    errors = []
    if u.scheme not in ALLOWED_PROXY_SCHEMES:
        errors.append("只支持 http:// 或 https:// 代理（Chromium 不支持带账号密码的 socks5）")
    if not u.hostname:
        errors.append("代理地址缺少主机")
    if not port:
        errors.append("代理地址缺少端口")
    return errors


_HOST_FORBIDDEN = frozenset("@/?#:[]")


def validate_proxy_host(host: str) -> None:
    """主机只允许域名或 IPv4：含 `@ / ? # : [ ]` 或空白即拒绝（IPv6 暂不支持）。

    否则 urlparse 会按最后一个 `@` 切分，把主机里的片段并进账号密码。
    """
    if not host or any(c in _HOST_FORBIDDEN or c.isspace() for c in host):
        raise ValueError("代理主机格式不正确")


def parse_provider_line(line: str) -> tuple[str, str]:
    """`IP|端口|账号|密码|到期日` → (`http://账号:密码@IP:端口`, 到期日 ISO 日期)。"""
    parts = [p.strip() for p in line.strip().split("|")]
    if len(parts) != _PROVIDER_FIELDS or not all(parts):
        raise ValueError("代理商格式应为 IP|端口|账号|密码|到期日")
    host, port, user, password, expires = parts
    validate_proxy_host(host)
    if not port.isdigit():
        raise ValueError("端口必须是数字")
    try:
        datetime.strptime(expires, "%Y-%m-%d")
    except ValueError:
        raise ValueError("到期日格式应为 YYYY-MM-DD") from None
    url = f"http://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}"
    errors = validate_proxy_url(url)
    if errors:
        raise ValueError(errors[0])
    return url, expires


def display_proxy(url: str) -> str:
    """只显示 主机:端口，用于界面与日志。"""
    u = urlparse(url)
    return f"{u.hostname}:{u.port}"


@dataclass(frozen=True)
class ProxyParts:
    """拆开的代理地址；账号密码为解码后的原文。"""

    scheme: str
    host: str
    port: int
    username: str
    password: str


def split_proxy_url(url: str) -> ProxyParts:
    """URL → 各部分（账号密码已 unquote）。调用方应先用 validate_proxy_url 校验。"""
    u = urlparse(url)
    return ProxyParts(
        scheme=u.scheme, host=u.hostname or "", port=u.port or 0,
        username=unquote(u.username or ""), password=unquote(u.password or ""),
    )


def join_proxy_url(parts: ProxyParts) -> str:
    """各部分 → URL；账号密码按 quote(safe='') 编码，无账号时不带 @。"""
    netloc = f"{parts.host}:{parts.port}"
    if parts.username or parts.password:
        cred = f"{quote(parts.username, safe='')}:{quote(parts.password, safe='')}"
        netloc = f"{cred}@{netloc}"
    return f"{parts.scheme}://{netloc}"


def proxy_identity(url: str) -> str:
    """代理池去重键：先拆解再拼接后取 sha256，粘贴格式与手填 URL 一致，且不可还原凭证。"""
    p = split_proxy_url(url)
    raw = f"{p.scheme}://{p.username}:{p.password}@{p.host.lower()}:{p.port}"
    return hashlib.sha256(raw.encode()).hexdigest()


def judge_egress(current_ip: str | None, new_ip: str | None, other_ips: set[str]) -> EgressVerdict:
    """new_ip 为本次检查得到的出口 IP；other_ips 为其他启用店铺已确认的出口 IP。"""
    if new_ip is None:
        return "unreachable"
    if new_ip in other_ips:
        return "duplicate"
    if current_ip is not None and current_ip != new_ip:
        return "changed"
    return "ok"


def _expiry_moment(expires_at: str) -> datetime:
    if len(expires_at) == len("YYYY-MM-DD"):
        # 到期日当天整天有效（北京时间）
        day = datetime.strptime(expires_at, "%Y-%m-%d")
        return (day + timedelta(days=1)).replace(tzinfo=BEIJING)
    return datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def expiry_state(expires_at: str | None, now: datetime) -> ExpiryState:
    """距到期 ≤ 7 天为 expiring，已到期为 expired；未填写到期日视为不限。"""
    if not expires_at:
        return "ok"
    remaining = _expiry_moment(expires_at) - now
    if remaining <= timedelta(0):
        return "expired"
    if remaining <= EXPIRING_WITHIN:
        return "expiring"
    return "ok"
