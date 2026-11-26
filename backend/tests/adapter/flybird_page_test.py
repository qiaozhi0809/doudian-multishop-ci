"""飞鸽常驻页适配器：用假的上下文、页面、长连接，不启动浏览器。数据全部虚构。"""

import inspect

import pytest

from app.adapter.flybird.page import ImPage
from app.adapter.flybird.parse import ConvListResult, Message
from tests.adapter.flybird_parse_test import (
    LIST_PATH,
    SENT_ISO,
    cmd_frame,
    load,
    message_body,
    message_frame,
    pull_body,
)

WORKSPACE_URL = "https://im.jinritemai.com/pc_seller_v2/main/workspace"
WS_URL = "wss://ws.fxg.jinritemai.com/ws/v2?token=test-token&aid=1383"
LIST_URL = f"https://pigeon.jinritemai.com{LIST_PATH}?biz_type=4&pageNo=0"


class Emitter:
    def __init__(self):
        self.handlers: dict[str, list] = {}

    def on(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    async def emit(self, event, *args):
        for handler in list(self.handlers.get(event, [])):
            result = handler(*args)
            if inspect.isawaitable(result):
                await result


class FakeWebSocket(Emitter):
    def __init__(self, url):
        super().__init__()
        self.url = url


class FakeResponse:
    def __init__(self, url, body=None, error: Exception | None = None):
        self.url = url
        self._body = body
        self._error = error
        self.reads = 0

    async def json(self):
        self.reads += 1
        if self._error:
            raise self._error
        return self._body

    async def body(self):
        self.reads += 1
        if self._error:
            raise self._error
        return self._body


class FakePage(Emitter):
    def __init__(self, calls: list):
        super().__init__()
        self.calls = calls
        self._closed = False

    def on(self, event, handler):
        self.calls.append(("on", event))
        super().on(event, handler)

    async def goto(self, url):
        self.calls.append(("goto", url))

    async def reload(self):
        self.calls.append(("reload",))

    def is_closed(self):
        return self._closed

    async def user_closes(self):
        self._closed = True
        await self.emit("close", self)


class FakeContext(Emitter):
    def __init__(self, *, existing_page: bool = True, fail: str = ""):
        super().__init__()
        self.calls: list = []
        self.fail = fail
        self.pages = [FakePage(self.calls)] if existing_page else []

    def _record(self, *call):
        self.calls.append(call)
        if call[0] == self.fail:
            raise RuntimeError(f"{self.fail} 失败")

    async def add_init_script(self, script=None, path=None):
        self._record("add_init_script")

    async def route(self, pattern, handler):
        self._record("route", pattern)

    async def new_page(self):
        self._record("new_page")
        page = FakePage(self.calls)
        self.pages.append(page)
        return page

    async def close(self):
        self._record("close")


class Sinks:
    def __init__(self):
        self.received: list[tuple] = []

    def kinds(self):
        return [kind for kind, _ in self.received]


async def attach(context: FakeContext) -> tuple[ImPage, FakePage, Sinks]:
    sinks = Sinks()
    im_page = await ImPage.attach(
        context,
        on_frame=lambda raw: sinks.received.append(("frame", raw)),
        on_list=lambda result: sinks.received.append(("list", result)),
        on_messages=lambda messages: sinks.received.append(("messages", messages)),
    )
    return im_page, context.pages[0], sinks


async def open_socket(page: FakePage, url: str = WS_URL) -> FakeWebSocket:
    socket = FakeWebSocket(url)
    await page.emit("websocket", socket)
    return socket


def names(context: FakeContext) -> list[str]:
    return [call[0] for call in context.calls]


# ---- 打开顺序 ----


async def test_attach_installs_guard_before_navigation():
    context = FakeContext()

    await attach(context)

    steps = [call for call in context.calls if call[0] != "on"]
    assert [call[0] for call in steps] == ["add_init_script", "route", "goto"]
    assert steps[-1] == ("goto", WORKSPACE_URL)


async def test_listeners_registered_before_navigation():
    context = FakeContext()

    await attach(context)

    before_goto = context.calls[: names(context).index("goto")]
    assert {("on", "websocket"), ("on", "response")} <= set(before_goto)


@pytest.mark.parametrize("step", ["add_init_script", "route"])
async def test_guard_install_failure_does_not_open_page(step):
    context = FakeContext(existing_page=False, fail=step)

    with pytest.raises(RuntimeError):
        await attach(context)

    assert "new_page" not in names(context)
    assert "goto" not in names(context)


async def test_attach_reuses_existing_page():
    context = FakeContext()
    existing = context.pages[0]

    im_page, _, _ = await attach(context)

    assert im_page.page is existing
    assert "new_page" not in names(context)


async def test_attach_creates_page_when_none():
    context = FakeContext(existing_page=False)

    im_page, page, _ = await attach(context)

    assert im_page.page is page
    assert names(context).count("new_page") == 1


# ---- 长连接 ----


async def test_message_frame_forwarded_to_on_messages():
    _, page, sinks = await attach(FakeContext())
    socket = await open_socket(page)
    raw = message_frame(message_body())

    await socket.emit("framereceived", raw)

    assert sinks.received == [
        ("frame", raw),
        ("messages", [Message("1001", "msg-test-1", "buyer", "在吗", SENT_ISO)]),
    ]


async def test_frame_without_messages_only_reaches_on_frame():
    _, page, sinks = await attach(FakeContext())
    socket = await open_socket(page)

    await socket.emit("framereceived", cmd_frame(16001))

    assert sinks.kinds() == ["frame"]


@pytest.mark.parametrize("url", [
    "wss://frontier.snssdk.com/ws/v2",
    "wss://ws.fxg.jinritemai.com.example.test/ws/v2",
    "wss://example.test/ws/v2?next=ws.fxg.jinritemai.com",
])
async def test_frames_from_other_hosts_ignored(url):
    _, page, sinks = await attach(FakeContext())
    socket = await open_socket(page, url)

    await socket.emit("framereceived", message_frame(message_body()))

    assert sinks.received == []


async def test_text_frames_ignored():
    _, page, sinks = await attach(FakeContext())
    socket = await open_socket(page)

    await socket.emit("framereceived", "hi")

    assert sinks.received == []


async def test_only_received_frames_are_observed():
    _, page, _ = await attach(FakeContext())

    socket = await open_socket(page)

    assert list(socket.handlers) == ["framereceived"]


async def test_ws_reconnect_keeps_listening():
    im_page, page, sinks = await attach(FakeContext())
    first = await open_socket(page)
    await first.emit("framereceived", cmd_frame(16001))
    await first.emit("close", first)
    second = await open_socket(page)

    await second.emit("framereceived", message_frame(message_body()))

    assert sinks.kinds() == ["frame", "frame", "messages"]
    assert not im_page.closed


# ---- 会话列表 ----


async def test_conv_list_response_parsed_and_forwarded():
    _, page, sinks = await attach(FakeContext())

    await page.emit("response", FakeResponse(LIST_URL, load("conv_list_ok.json")))

    assert sinks.received == [("list", ConvListResult(0, {"1001": "conv-test-1"}))]


async def test_non_list_response_ignored():
    _, page, sinks = await attach(FakeContext())
    response = FakeResponse(f"https://im.jinritemai.com{LIST_PATH}", {"code": 0, "data": []})

    await page.emit("response", response)

    assert sinks.received == []
    assert response.reads == 0  # 无关响应连正文都不读


async def test_bad_json_ignored():
    _, page, sinks = await attach(FakeContext())
    response = FakeResponse(LIST_URL, error=ValueError("不是 JSON"))

    await page.emit("response", response)

    assert sinks.received == []


# ---- 刷新与关闭 ----


async def test_reload_reloads_page():
    context = FakeContext()
    im_page, _, _ = await attach(context)

    await im_page.reload()

    assert names(context)[-1] == "reload"


async def test_closed_when_page_closes():
    im_page, page, _ = await attach(FakeContext())
    assert not im_page.closed

    await page.user_closes()

    assert im_page.closed


async def test_closed_when_context_closes():
    context = FakeContext()
    im_page, _, _ = await attach(context)

    await context.emit("close", context)

    assert im_page.closed


async def test_does_not_close_context():
    context = FakeContext()
    im_page, page, _ = await attach(context)

    await im_page.reload()
    await page.user_closes()

    assert "close" not in names(context)


# ---- 增量拉取 ----

PULL_URL = "https://fxg.jinritemai.com/pigeon_im/v3/message/get_user_message?PIGEON_BIZ_TYPE=2"


async def test_pull_response_messages_forwarded():
    _, page, sinks = await attach(FakeContext())

    await page.emit("response", FakeResponse(PULL_URL, pull_body([message_body()])))

    assert sinks.received == [
        ("messages", [Message("1001", "msg-test-1", "buyer", "在吗", SENT_ISO)]),
    ]


async def test_empty_pull_response_not_forwarded():
    _, page, sinks = await attach(FakeContext())

    await page.emit("response", FakeResponse(PULL_URL, pull_body()))

    assert sinks.received == []


async def test_pull_body_unavailable_ignored():
    _, page, sinks = await attach(FakeContext())

    await page.emit("response", FakeResponse(PULL_URL, error=RuntimeError("页面已关闭")))

    assert sinks.received == []
