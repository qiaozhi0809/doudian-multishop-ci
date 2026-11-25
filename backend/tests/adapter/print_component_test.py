"""打印组件 WebSocket 客户端：探测、打印、回执超时（假连接，无网络）。"""

import asyncio
import json

from app.adapter.print import protocol
from app.adapter.print.component import PrintComponent
from app.adapter.print.ports import PRINT_COMPONENT_ORIGIN


class FakeSocket:
    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.sent: list[str] = []

    async def send(self, text):
        self.sent.append(text)

    async def recv(self):
        if not self.incoming:
            raise TimeoutError("没有更多消息")
        item = self.incoming.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeConnection:
    def __init__(self, socket):
        self.socket = socket

    async def __aenter__(self):
        return self.socket

    async def __aexit__(self, *exc):
        return False


class FakeConnector:
    """每次连接按序取出一个 FakeSocket；connect 参数可断言。"""

    def __init__(self, sockets, *, error=None):
        self.sockets = list(sockets)
        self.error = error
        self.calls: list[tuple] = []

    def __call__(self, url, origin, open_timeout):
        self.calls.append((url, origin, open_timeout))
        if self.error is not None:
            raise self.error
        return FakeConnection(self.sockets.pop(0))


def component(sockets, **kw):
    connector = FakeConnector(sockets, error=kw.pop("error", None))
    return PrintComponent(connect=connector, probe_timeout=0.05,
                          result_timeout=0.05, **kw), connector


def test_probes_with_get_printers_and_parses_reply():
    sock = FakeSocket([json.dumps({
        "cmd": "getPrinters", "requestID": "ignored",
        "defaultPrinter": "A", "printers": [{"name": "A"}, {"name": "B"}],
    })])
    comp, connector = component([sock])

    result = asyncio.run(comp.probe())

    assert result.available
    assert result.default_printer == "A"
    assert result.printers == ("A", "B")
    assert result.error is None
    url, origin, _ = connector.calls[0]
    assert url.endswith(":13999")
    assert origin == PRINT_COMPONENT_ORIGIN
    sent = json.loads(sock.sent[0])
    assert sent["cmd"] == "getPrinters" and sent["version"] == 2


def test_probe_reports_component_not_started():
    comp, _ = component([], error=OSError("connection refused"))

    result = asyncio.run(comp.probe())

    assert not result.available
    assert result.printers == ()
    assert "打印组件" in result.error


def test_probe_timeout_is_unavailable():
    sock = FakeSocket([TimeoutError("timeout")])
    comp, _ = component([sock])

    result = asyncio.run(comp.probe())

    assert not result.available
    assert result.error


def test_print_sends_documents_and_waits_for_notify():
    sock = FakeSocket([
        json.dumps({"cmd": "print", "requestID": "r", "status": "success"}),
        json.dumps({"cmd": "notifyPrintResult", "requestID": "r", "status": "success"}),
    ])
    comp, _ = component([sock])
    docs = [protocol.DocumentSpec(
        waybill_no="w1", print_data="P", sign="S", template_url="U",
        params=None, custom_print_data=None, custom_template_url=None)]

    outcome = asyncio.run(comp.print_documents("Printer A", docs))

    assert outcome.ok
    message = json.loads(sock.sent[0])
    assert message["cmd"] == "print"
    assert message["task"]["printer"] == "Printer A"
    assert message["task"]["documents"][0]["standard"]["encryptedData"] == "P"


def test_print_reports_component_failure():
    sock = FakeSocket([
        json.dumps({"cmd": "print", "requestID": "r", "status": "success"}),
        json.dumps({"cmd": "notifyPrintResult", "requestID": "r", "status": "failed",
                    "printStatus": [{"status": "failed", "detail": ""}]}),
    ])
    comp, _ = component([sock])

    outcome = asyncio.run(comp.print_documents("A", []))

    assert not outcome.ok
    assert outcome.code == protocol.RESULT_COMPONENT_FAILED


def test_print_ack_rejection_fails_fast():
    sock = FakeSocket([json.dumps({
        "cmd": "print", "requestID": "r", "status": "failed", "msg": "模板不存在"})])
    comp, _ = component([sock])

    outcome = asyncio.run(comp.print_documents("A", []))

    assert not outcome.ok
    assert "模板不存在" in outcome.detail


def test_print_timeout_returns_not_ok():
    sock = FakeSocket([
        json.dumps({"cmd": "print", "requestID": "r", "status": "success"}),
        TimeoutError("timeout"),
    ])
    comp, _ = component([sock])

    outcome = asyncio.run(comp.print_documents("A", []))

    assert not outcome.ok
    assert outcome.code == protocol.RESULT_NO_RESPONSE


def test_print_connection_error_is_unavailable():
    comp, _ = component([], error=ConnectionRefusedError("refused"))

    outcome = asyncio.run(comp.print_documents("A", []))

    assert not outcome.ok
    assert outcome.code == protocol.RESULT_UNAVAILABLE
