"""出口 IP 探测：经该店出口请求 IP 回显地址。"""

import asyncio
import ipaddress
from collections.abc import Awaitable, Callable

from app.adapter.doudian.errors import TransientError
from app.adapter.doudian.transport import CurlTransport, Transport

PROBE_TIMEOUT_S = 10

FetchIp = Callable[[str | None], Awaitable[str | None]]


def _default_factory(proxy: str | None) -> Transport:
    return CurlTransport(proxy, timeout_s=PROBE_TIMEOUT_S)


def make_fetch_ip(
    echo_url: str, transport_factory: Callable[[str | None], Transport] = _default_factory
) -> FetchIp:
    """返回 fetch_ip(proxy)：proxy 为 None 即直连探测；失败、超时或回显不是 IP 一律返回 None。"""

    async def fetch_ip(proxy: str | None) -> str | None:
        transport = transport_factory(proxy)
        try:
            resp = await asyncio.wait_for(transport.request("GET", echo_url), PROBE_TIMEOUT_S)
        except (TransientError, TimeoutError):
            return None
        if resp.status != 200:
            return None
        try:
            return str(ipaddress.ip_address(resp.body.decode("ascii", "ignore").strip()))
        except ValueError:
            return None

    return fetch_ip
