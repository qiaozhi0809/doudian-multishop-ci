"""Host 白名单：防 DNS 重绑定。不在白名单的请求返回 421。"""

import json

from starlette.types import ASGIApp, Receive, Scope, Send

DEV_FRONTEND_HOST = "localhost:5173"


def allowed_hosts(port: int, dev_mode: bool) -> frozenset[str]:
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    if dev_mode:
        hosts.add(DEV_FRONTEND_HOST)
    return frozenset(hosts)


class HostGuard:
    def __init__(self, app: ASGIApp, hosts: frozenset[str]) -> None:
        self.app = app
        self.hosts = hosts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            host = dict(scope["headers"]).get(b"host", b"").decode("latin-1").lower()
            if host not in self.hosts:
                await self._reject(scope, send)
                return
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(scope: Scope, send: Send) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        body = json.dumps({"error": {
            "type": "HostNotAllowed", "message": "不允许的 Host", "shop_id": None, "detail": None,
        }}).encode()
        await send({"type": "http.response.start", "status": 421, "headers": [
            (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
        ]})
        await send({"type": "http.response.body", "body": body})
