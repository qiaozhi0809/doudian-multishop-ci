"""测试替身：按序返回预设响应并记录请求。"""

import json as jsonlib
from dataclasses import dataclass, field
from typing import Any

from app.adapter.doudian.transport import TransportResponse


def ok(data: Any = None, code: Any = 0) -> TransportResponse:
    return TransportResponse(200, jsonlib.dumps({"code": code, "msg": "", "data": data}).encode())


def reply(body: dict, status: int = 200) -> TransportResponse:
    return TransportResponse(status, jsonlib.dumps(body).encode())


@dataclass
class FakeTransport:
    responses: list[TransportResponse | Exception]
    requests: list[dict] = field(default_factory=list)

    async def request(self, method, url, *, params=None, json=None, data=None,
                      cookies=None, headers=None) -> TransportResponse:
        self.requests.append({
            "method": method, "url": url, "params": params, "json": json,
            "data": data, "cookies": cookies, "headers": headers,
        })
        assert self.responses, "FakeTransport 没有预设响应了"
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
