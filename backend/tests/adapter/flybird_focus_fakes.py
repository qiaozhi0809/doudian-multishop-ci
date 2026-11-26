"""置前测试用的假页面：按调用顺序记录 CDP 窗口调用、置前与点击。数据全部虚构。"""

from typing import Any

WINDOW_ID = 7
_PREFIX = "Browser."


class FakeCdpSession:
    def __init__(self, page: "FakeFocusPage") -> None:
        self._page = page

    async def send(self, method: str, params: dict | None = None) -> dict:
        assert method.startswith(_PREFIX), method
        name = method.removeprefix(_PREFIX)
        self._page.calls.append((name,) if params is None else (name, params))
        if self._page.window_error is not None:
            raise self._page.window_error
        return {"windowId": WINDOW_ID}

    async def detach(self) -> None:
        self._page.calls.append(("detach",))


class _FakeContext:
    def __init__(self, page: "FakeFocusPage") -> None:
        self._page = page

    async def new_cdp_session(self, page: "FakeFocusPage") -> FakeCdpSession:
        assert page is self._page
        return FakeCdpSession(page)


class FakeLocator:
    """会话列表元素：每个会话是一段可见文本。"""

    def __init__(self, page: "FakeFocusPage", texts: list[str]) -> None:
        self._page = page
        self._texts = texts

    def filter(self, *, has_text: str) -> "FakeLocator":
        return FakeLocator(self._page, [t for t in self._texts if has_text in t])

    async def count(self) -> int:
        return len(self._texts)

    async def click(self) -> None:
        assert len(self._texts) == 1, "定位不唯一时 Playwright 会报错"
        if self._page.click_error is not None:
            raise self._page.click_error
        self._page.calls.append(("click", self._texts[0]))


class FakeFocusPage:
    def __init__(self, conversations: list[str] | None = None) -> None:
        self.conversations = list(conversations or [])
        self.calls: list[tuple[Any, ...]] = []
        self.selectors: list[str] = []
        self.window_error: Exception | None = None
        self.click_error: Exception | None = None
        self.context = _FakeContext(self)

    async def bring_to_front(self) -> None:
        self.calls.append(("bring_to_front",))

    def locator(self, selector: str) -> FakeLocator:
        self.selectors.append(selector)
        return FakeLocator(self, self.conversations)

    def clicked(self) -> list[str]:
        return [call[1] for call in self.calls if call[0] == "click"]
