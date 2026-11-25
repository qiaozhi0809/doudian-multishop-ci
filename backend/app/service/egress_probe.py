"""出口 IP 探测：经该店出口请求 IP 回显地址。"""

import asyncio
import ipaddress
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from app.adapter.doudian.errors import EgressUnavailable, TransientError
from app.adapter.doudian.transport import CurlTransport, Transport

PROBE_TIMEOUT_S = 10

FetchIp = Callable[[str | None], Awaitable[str | None]]

ProbeReason = Literal["timeout", "proxy_unavailable", "network", "bad_echo"]


@dataclass(frozen=True)
class ProbeResult:
    ip: str | None
    reason: ProbeReason | None  # 成功时为 None


Probe = Callable[[str | None], Awaitable[ProbeResult]]


def _default_factory(proxy: str | None) -> Transport:
    return CurlTransport(proxy, timeout_s=PROBE_TIMEOUT_S)


def make_probe(
    echo_url: str, transport_factory: Callable[[str | None], Transport] = _default_factory
) -> Probe:
    """返回 probe(proxy)：proxy 为 None 即直连探测；失败时给出细分原因。"""

    async def probe(proxy: str | None) -> ProbeResult:
        transport = transport_factory(proxy)
        try:
            resp = await asyncio.wait_for(transport.request("GET", echo_url), PROBE_TIMEOUT_S)
        except TimeoutError:
            return ProbeResult(None, "timeout")
        except EgressUnavailable:
            return ProbeResult(None, "proxy_unavailable")
        except TransientError:
            return ProbeResult(None, "network")
        if resp.status != 200:
            return ProbeResult(None, "bad_echo")
        try:
            ip = str(ipaddress.ip_address(resp.body.decode("ascii", "ignore").strip()))
        except ValueError:
            return ProbeResult(None, "bad_echo")
        return ProbeResult(ip, None)

    return probe


def make_fetch_ip(
    echo_url: str, transport_factory: Callable[[str | None], Transport] = _default_factory
) -> FetchIp:
    """返回 fetch_ip(proxy)：失败、超时或回显不是 IP 一律返回 None。"""
    probe = make_probe(echo_url, transport_factory)

    async def fetch_ip(proxy: str | None) -> str | None:
        return (await probe(proxy)).ip

    return fetch_ip
