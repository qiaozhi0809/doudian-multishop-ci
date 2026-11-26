"""「在飞鸽中回复」：把该店常驻页窗口移回屏幕并置前，按买家昵称点开该会话一次。

全系统唯一的页面点击，只在所有者点按钮时执行；不输入、不按键、不发送。
点开会话时页面发出的标已读仍由 read_guard 拦下。
"""

from typing import Any

from playwright.async_api import CDPSession, Page

from app.adapter.flybird import endpoints as ep


async def _window_call(
    session: CDPSession, method: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """浏览器窗口的 CDP 调用（不是长连接发帧）。只读守卫只放行这一处，方法名须是字面量。"""
    return await session.send(method, params)


async def _show_window(page: Page) -> None:
    session = await page.context.new_cdp_session(page)  # 走同一条浏览器连接
    try:
        window = await _window_call(session, "Browser.getWindowForTarget")
        target = {"windowId": window["windowId"]}
        # 最小化状态下不能直接设位置：先恢复 normal，再移回屏幕
        await _window_call(
            session, "Browser.setWindowBounds", {**target, "bounds": ep.FOCUS_RESTORE})
        await _window_call(
            session, "Browser.setWindowBounds", {**target, "bounds": ep.FOCUS_BOUNDS})
    finally:
        await session.detach()
    await page.bring_to_front()


async def focus_conversation(page: Page, buyer_name: str | None) -> bool:
    """点开了会话返回 True。定位到的不是恰好 1 个就不点、返回 False。

    会话元素上没有会话编号：有昵称按文本定位；没有昵称时只在列表里仅一个会话时点它。
    """
    await _show_window(page)
    conversations = page.locator(ep.CONVERSATION_SELECTOR)
    if buyer_name:
        conversations = conversations.filter(has_text=buyer_name)
    if await conversations.count() != 1:
        return False
    await conversations.click()
    return True
