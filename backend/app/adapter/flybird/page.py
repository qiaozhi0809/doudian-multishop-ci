"""飞鸽常驻页：打开工作台，只被动监听页面自己收到的长连接帧与会话列表响应。

浏览器由登记表打开和关闭，这里只用交进来的上下文。长连接断开重连是常态
（docs/api/flybird.md §4），不当错误。帧与消息内容不进日志。
"""

from collections.abc import Callable
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext, Page, Response, WebSocket

from app.adapter.flybird import endpoints as ep
from app.adapter.flybird import read_guard
from app.adapter.flybird.parse import (
    ConvListResult,
    Message,
    is_conv_list_url,
    is_msg_pull_url,
    parse_conv_list,
    parse_message_frame,
    parse_message_pull,
)

FrameSink = Callable[[bytes], None]
ListSink = Callable[[ConvListResult], None]
MessageSink = Callable[[list[Message]], None]


class ImPage:
    def __init__(
        self, page: Page, *, on_frame: FrameSink, on_list: ListSink, on_messages: MessageSink
    ) -> None:
        self._page = page
        self._on_frame = on_frame
        self._on_list = on_list
        self._on_messages = on_messages
        self._closed = False

    @classmethod
    async def attach(
        cls, context: BrowserContext, *,
        on_frame: FrameSink, on_list: ListSink, on_messages: MessageSink,
    ) -> "ImPage":
        """先装已读拦截，再注册监听，最后打开工作台；拦截装不上就不打开页面。"""
        await read_guard.install(context)
        page = context.pages[0] if context.pages else await context.new_page()
        im_page = cls(page, on_frame=on_frame, on_list=on_list, on_messages=on_messages)
        context.on("close", im_page._mark_closed)
        page.on("close", im_page._mark_closed)
        page.on("websocket", im_page._watch_socket)
        page.on("response", im_page._read_response)
        await page.goto(ep.WORKSPACE_URL)
        return im_page

    @property
    def page(self) -> Page:
        return self._page

    @property
    def closed(self) -> bool:
        """页面或上下文已关闭。"""
        return self._closed or self._page.is_closed()

    async def reload(self) -> None:
        await self._page.reload()

    def _mark_closed(self, _source: object) -> None:
        self._closed = True

    def _watch_socket(self, socket: WebSocket) -> None:
        if urlsplit(socket.url).hostname == ep.WS_HOST:
            socket.on("framereceived", self._read_frame)

    def _read_frame(self, payload: bytes | str) -> None:
        if not isinstance(payload, bytes):
            return
        self._on_frame(payload)
        messages = parse_message_frame(payload)
        if messages:
            self._on_messages(messages)

    async def _read_response(self, response: Response) -> None:
        if is_msg_pull_url(response.url):
            await self._read_pull(response)
            return
        if not is_conv_list_url(response.url):
            return
        try:
            body = await response.json()
        except Exception:  # noqa: BLE001 - 非 JSON，或页面刷新、关闭时正文已取不到
            return
        self._on_list(parse_conv_list(body))

    async def _read_pull(self, response: Response) -> None:
        """长连接断开期间与重连后的消息只经页面自己的增量拉取到达（flybird.md §4）。"""
        try:
            body = await response.body()
        except Exception:  # noqa: BLE001 - 页面刷新、关闭时正文已取不到
            return
        messages = parse_message_pull(body)
        if messages:
            self._on_messages(messages)
