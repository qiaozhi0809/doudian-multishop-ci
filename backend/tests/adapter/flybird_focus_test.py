"""飞鸽置前到会话：窗口恢复并移回屏幕、置前、按买家昵称唯一定位后点一次。数据全部虚构。"""

import pytest

from app.adapter.flybird.focus import focus_conversation
from tests.adapter.flybird_focus_fakes import WINDOW_ID, FakeFocusPage

MINE = "测试买家\n在吗"
OTHER = "测试顾客\n你好"
BOUNDS = {"left": 0, "top": 0, "width": 1400, "height": 900}


async def test_restore_then_bounds_then_bring_to_front_then_single_click():
    page = FakeFocusPage([MINE, OTHER])

    assert await focus_conversation(page, "测试买家") is True

    assert page.calls == [
        ("getWindowForTarget",),
        ("setWindowBounds", {"windowId": WINDOW_ID, "bounds": {"windowState": "normal"}}),
        ("setWindowBounds", {"windowId": WINDOW_ID, "bounds": BOUNDS}),
        ("detach",),
        ("bring_to_front",),
        ("click", MINE),
    ]


async def test_locates_by_buyer_name():
    page = FakeFocusPage([OTHER, MINE])

    assert await focus_conversation(page, "测试买家") is True

    assert page.selectors == ['[data-kora="conversation"]']
    assert page.clicked() == [MINE]


@pytest.mark.parametrize("conversations", [
    [], [OTHER], [MINE, "测试买家\n还在吗"],
])
async def test_ambiguous_or_missing_returns_false_without_click(conversations):
    page = FakeFocusPage(conversations)

    assert await focus_conversation(page, "测试买家") is False

    assert page.clicked() == []
    assert page.calls[-1] == ("bring_to_front",)  # 窗口照样置前，由所有者自己找


@pytest.mark.parametrize("name", [None, ""])
async def test_no_name_single_conversation_clicked(name):
    page = FakeFocusPage([OTHER])

    assert await focus_conversation(page, name) is True

    assert page.clicked() == [OTHER]


@pytest.mark.parametrize("conversations", [[], [MINE, OTHER]])
async def test_no_name_multiple_conversations_not_clicked(conversations):
    page = FakeFocusPage(conversations)

    assert await focus_conversation(page, None) is False

    assert page.clicked() == []


async def test_window_session_detached_when_window_call_fails():
    page = FakeFocusPage([MINE])
    page.window_error = RuntimeError("没有窗口")

    with pytest.raises(RuntimeError):
        await focus_conversation(page, "测试买家")

    assert page.calls == [("getWindowForTarget",), ("detach",)]


async def test_name_in_other_preview_is_not_matched():
    page = FakeFocusPage(["测试顾客\n测试买家刚才说的那个", MINE])

    assert await focus_conversation(page, "测试买家") is True
    assert page.clicked() == [MINE]


async def test_longer_name_containing_buyer_name_is_not_matched():
    page = FakeFocusPage(["测试买家二号\n在吗"])

    assert await focus_conversation(page, "测试买家") is False
    assert page.clicked() == []
