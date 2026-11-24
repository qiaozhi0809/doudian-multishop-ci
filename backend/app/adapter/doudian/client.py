"""抖店 HTTP 客户端：注入公共参数、成功码归一化、错误分类、只读退避重试、审计回调。"""

import asyncio
import json
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from app.adapter.doudian.endpoints import AID, APPID, BASE_URL, Endpoint
from app.adapter.doudian.error_codes import RISK_CODES, SESSION_EXPIRED, SUCCESS_CODES
from app.adapter.doudian.errors import (
    BizRejected,
    EgressUnavailable,
    ParseError,
    RiskBlocked,
    SessionExpired,
    TransientError,
)
from app.adapter.doudian.pacer import ShopPacer
from app.adapter.doudian.transport import Transport, TransportResponse
from app.domain.audit import CallRecord
from app.shared.redact import redact_mapping, scrub_text

RETRY_DELAYS_S = (1, 2, 4)
_HOST = urlparse(BASE_URL).hostname or ""


@dataclass(frozen=True)
class ShopCredentials:
    shop_id: int
    cookies: list[dict] = field(repr=False)
    token: str = field(repr=False)
    device_headers: dict[str, str] = field(repr=False)


def _lid() -> int:
    return random.randint(10**11, 10**12 - 1)


def _cookie_matches(c: dict, path: str) -> bool:
    domain = str(c.get("domain", "")).lstrip(".")
    domain_ok = _HOST == domain or _HOST.endswith("." + domain)
    return domain_ok and path.startswith(c.get("path") or "/")


class FxgClient:
    def __init__(
        self,
        transport: Transport,
        creds: ShopCredentials,
        pacer: ShopPacer,
        observer: Callable[[CallRecord], None],
        actor: str,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        lid_factory: Callable[[], int] = _lid,
    ) -> None:
        self._transport = transport
        self._creds = creds
        self._pacer = pacer
        self._observer = observer
        self._actor = actor
        self._sleep = sleep
        self._lid = lid_factory

    async def call(
        self, ep: Endpoint, params: dict | None = None, body: dict | None = None
    ) -> dict:
        started = time.monotonic()
        summary: dict = {"code": None}
        result = "ok"
        try:
            await self._pacer.wait()
            resp = await self._send_with_retry(ep, params or {}, body or {})
            return self._parse(resp, summary)
        except Exception as e:
            result = type(e).__name__
            summary["error"] = scrub_text(str(e))
            raise
        finally:
            self._observe(ep, params or {}, summary, result, started)

    async def _send_with_retry(self, ep: Endpoint, params: dict, body: dict) -> TransportResponse:
        delays = iter(() if ep.write else RETRY_DELAYS_S)
        while True:
            try:
                return self._check_status(await self._send(ep, params, body))
            except EgressUnavailable:
                raise
            except TransientError:
                delay = next(delays, None)
                if delay is None:
                    raise
                await self._sleep(delay)

    async def _send(self, ep: Endpoint, params: dict, body: dict) -> TransportResponse:
        common = {
            "appid": APPID, "aid": AID, "_bid": ep.bid,
            "__token": self._creds.token, "_lid": self._lid(),
        }
        query: dict[str, Any] = dict(params)
        payload: dict[str, Any] | None = None
        if ep.body == "query":
            query = {**common, **params, **ep.fixed_params}
        else:
            payload = {**body, **common, **ep.fixed_params}
        return await self._transport.request(
            ep.method, BASE_URL + ep.path,
            params=query or None,
            json=payload if ep.body == "json" else None,
            data=payload if ep.body == "form" else None,
            cookies=self._cookies_for(ep.path),
            headers=dict(self._creds.device_headers),
        )

    def _cookies_for(self, path: str) -> dict[str, str]:
        return {
            c["name"]: c["value"] for c in self._creds.cookies if _cookie_matches(c, path)
        }

    @staticmethod
    def _check_status(resp: TransportResponse) -> TransportResponse:
        if resp.status >= 500 or resp.status == 429:
            raise TransientError(f"HTTP {resp.status}")
        if resp.status >= 400:
            raise BizRejected(str(resp.status), "HTTP 错误")
        return resp

    @staticmethod
    def _parse(resp: TransportResponse, summary: dict) -> dict:
        try:
            data = json.loads(resp.body)
        except ValueError as e:
            raise ParseError("响应不是 JSON") from e
        if not isinstance(data, dict) or "code" not in data:
            raise ParseError("响应缺少 code 字段")
        code = str(data["code"])
        msg = str(data.get("msg") or data.get("message") or "")
        summary.update({"code": code, "msg": scrub_text(msg)})
        if code in SUCCESS_CODES:
            return data
        if code == SESSION_EXPIRED:
            raise SessionExpired(msg or "会话失效")
        if code in RISK_CODES:
            raise RiskBlocked(code, msg)
        raise BizRejected(code, msg)

    def _observe(
        self, ep: Endpoint, params: dict, resp_summary: dict, result: str, started: float
    ) -> None:
        self._observer(CallRecord(
            shop_id=self._creds.shop_id,
            action=ep.name,
            actor=self._actor,
            req_summary={"method": ep.method, "path": ep.path, "params": redact_mapping(params)},
            resp_summary=resp_summary,
            result=result,
            duration_ms=int((time.monotonic() - started) * 1000),
        ))
