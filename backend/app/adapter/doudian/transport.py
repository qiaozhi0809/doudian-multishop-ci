"""发送层：生产用 curl_cffi，测试用 FakeTransport 替换。"""

from dataclasses import dataclass
from typing import Any, Protocol

from curl_cffi.requests import AsyncSession
from curl_cffi.requests import exceptions as cx

from app.adapter.doudian.errors import EgressUnavailable, TransientError

REQUEST_TIMEOUT_S = 30


@dataclass(frozen=True)
class TransportResponse:
    status: int
    body: bytes


class Transport(Protocol):
    async def request(
        self, method: str, url: str, *, params: dict | None = None, json: Any = None,
        data: Any = None, cookies: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> TransportResponse: ...


class CurlTransport:
    """proxy 为 None 即直连；配置了代理后连接失败只会抛 EgressUnavailable，不会改走直连。"""

    def __init__(
        self, proxy: str | None, impersonate: str = "chrome", timeout_s: float = REQUEST_TIMEOUT_S
    ) -> None:
        self._proxy = proxy
        self._impersonate = impersonate
        self._timeout_s = timeout_s

    async def request(
        self, method: str, url: str, *, params: dict | None = None, json: Any = None,
        data: Any = None, cookies: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> TransportResponse:
        try:
            async with AsyncSession(impersonate=self._impersonate) as s:
                resp = await s.request(
                    method, url, params=params, json=json, data=data, cookies=cookies,
                    headers=headers, proxy=self._proxy, timeout=self._timeout_s,
                    allow_redirects=False,
                )
            return TransportResponse(resp.status_code, resp.content)
        except cx.RequestException as e:
            # 异常信息可能带代理 URL（含账号密码），一律不向外传递原文
            raise self._classify(e) from None

    def _classify(self, e: cx.RequestException) -> TransientError:
        proxy_failed = isinstance(e, (cx.ProxyError, cx.InvalidProxyURL)) or (
            isinstance(e, cx.ConnectionError) and not isinstance(e, cx.SSLError)
        )
        if self._proxy is not None and proxy_failed:
            return EgressUnavailable("出口代理不可用")
        return TransientError(f"网络错误: {type(e).__name__}")
