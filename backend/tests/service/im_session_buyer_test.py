"""飞鸽单店循环里的买家昵称：按会话保留最近一次，只在内存。数据全部虚构。"""

from dataclasses import replace

from structlog.testing import capture_logs

from app.adapter.flybird.parse import Message
from tests.service.im_session_test import msg, running


def named(message_id: str, name: str = "测试买家", **kwargs) -> Message:
    return replace(msg(message_id, **kwargs), buyer_name=name)


async def test_snapshot_keeps_latest_buyer_name():
    async with running(history=[msg("msg-test-0")]) as rig:
        assert rig.session.snapshot()[0].buyer_name is None  # 历史消息没有昵称

        await rig.receive(named("msg-test-1", at=1), named("msg-test-9", conv="1002", at=1))
        await rig.receive(named("msg-test-2", "测试买家二", at=2))
        await rig.receive(msg("msg-test-3", at=3), msg("msg-test-4", "agent", at=4))

        names = {v.conversation_id: v.buyer_name for v in rig.session.snapshot()}
        assert names == {"1001": "测试买家二", "1002": "测试买家"}
        assert "测试买家" not in repr(rig.session.snapshot())


async def test_late_arrival_does_not_replace_newer_buyer_name():
    async with running() as rig:
        await rig.receive(named("msg-test-2", "测试买家二", at=2))
        await rig.receive(named("msg-test-1", at=1))

        assert rig.session.snapshot()[0].buyer_name == "测试买家二"


async def test_buyer_name_outlives_message_tail():
    async with running() as rig:
        await rig.receive(named("msg-test-first"))
        await rig.receive(*(msg(f"msg-test-{i}", "agent", at=i) for i in range(1, 52)))

        assert rig.session.snapshot()[0].buyer_name == "测试买家"


async def test_redelivered_history_message_supplies_buyer_name():
    """重启后历史里没有昵称；页面再次拉到同一条消息时补上，但不算新消息。"""
    async with running(history=[msg("msg-test-1")]) as rig:
        await rig.receive(named("msg-test-1"))

        assert rig.session.snapshot()[0].buyer_name == "测试买家"
        assert rig.saved == []


async def test_buyer_name_not_in_event_payloads():
    with capture_logs() as logs:
        async with running(history=[named("msg-test-1", at=-200)]) as rig:
            await rig.receive(named("msg-test-2"))
            rig.session.stop()
            await rig.finish()

            assert rig.events
            assert "测试买家" not in str(rig.events)
    assert "测试买家" not in str(logs)
