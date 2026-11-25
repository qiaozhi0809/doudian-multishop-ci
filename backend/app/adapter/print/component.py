"""官方打印组件 WebSocket 客户端（flows 10 节）：探测与打印。

组件用自签证书（跳过校验）、要求 Origin 为抖店页面来源；连接参数来自 ports。
连接函数可注入，测试不碰真实网络。
"""

import asyncio
import json
import ssl
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import structlog

from app.adapter.print import protocol
from app.adapter.print.ports import (
    PRINT_COMPONENT_ORIGIN,
    PRINT_COMPONENT_URL,
    PRINT_RESULT_TIMEOUT_S,
    PROBE_TIMEOUT_S,
)

log = structlog.get_logger()

COMPONENT_HINT = "请先启动抖店官方打印组件"


class SocketLike(Protocol):
    async def send(self, message: str) -> None: ...

    async def recv(self) -> str | bytes: ...


@dataclass(frozen=True)
class PrinterProbe:
    available: bool
    default_printer: str | None = None
    printers: tuple[str, ...] = ()
    error: str | None = None


def _request_id() -> str:
    return f"dd_{uuid.uuid4().hex}"


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def default_connect(url: str, origin: str, open_timeout: float):
    """真实连接：wss + 跳过自签证书校验；延迟导入 websockets，纯协议测试不依赖它。"""
    from websockets.asyncio.client import connect

    return connect(url, origin=origin, ssl=_ssl_context(), open_timeout=open_timeout)


class PrintComponent:
    def __init__(
        self, *, url: str = PRINT_COMPONENT_URL, origin: str = PRINT_COMPONENT_ORIGIN,
        connect=default_connect, probe_timeout: float = PROBE_TIMEOUT_S,
        result_timeout: float = PRINT_RESULT_TIMEOUT_S,
    ) -> None:
        self._url = url
        self._origin = origin
        self._connect = connect
        self._probe_timeout = probe_timeout
        self._result_timeout = result_timeout

    async def probe(self) -> PrinterProbe:
        """getPrinters 探测；超时或连接失败即视为组件未启动。"""
        try:
            async with self._connect(
                self._url, self._origin, self._probe_timeout
            ) as socket:
                await socket.send(
                    json.dumps(protocol.build_get_printers(_request_id())))
                async with asyncio.timeout(self._probe_timeout):
                    message = await self._read_printers(socket)
        except Exception as e:  # 外部边界：任何连接/协议错误都归为「组件不可用」
            return PrinterProbe(False, error=f"{COMPONENT_HINT}（{type(e).__name__}）")
        default, printers = protocol.parse_printers(message)
        return PrinterProbe(True, default, printers)

    async def print_documents(
        self, printer: str, documents: Sequence[protocol.DocumentSpec]
    ) -> protocol.PrintOutcome:
        """提交打印并等待 notifyPrintResult；其余失败都转成可记录的 outcome。"""
        request_id = _request_id()
        message = protocol.build_print_message(
            request_id=request_id, printer=printer,
            documents=protocol.build_documents(documents))
        try:
            async with self._connect(
                self._url, self._origin, self._probe_timeout
            ) as socket:
                await socket.send(json.dumps(message))
                async with asyncio.timeout(self._result_timeout):
                    return await self._read_result(socket)
        except TimeoutError:
            return protocol.PrintOutcome(
                False, protocol.RESULT_NO_RESPONSE, "等待打印组件回执超时")
        except Exception as e:
            return protocol.PrintOutcome(
                False, protocol.RESULT_UNAVAILABLE,
                f"{COMPONENT_HINT}（{type(e).__name__}）")

    @staticmethod
    async def _read_printers(socket: SocketLike) -> dict[str, Any]:
        while True:
            message = await _receive(socket)
            if message.get("cmd") == protocol.CMD_GET_PRINTERS:
                return message

    @staticmethod
    async def _read_result(socket: SocketLike) -> protocol.PrintOutcome:
        while True:
            message = await _receive(socket)
            cmd = message.get("cmd")
            if cmd == protocol.CMD_PRINT:
                accepted, detail = protocol.parse_ack(message)
                if not accepted:
                    return protocol.PrintOutcome(
                        False, protocol.RESULT_COMPONENT_FAILED, detail)
            elif cmd in protocol.NOTIFY_COMMANDS:
                return protocol.parse_print_result(message)


async def _receive(socket: SocketLike) -> dict[str, Any]:
    raw = await socket.recv()
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}
