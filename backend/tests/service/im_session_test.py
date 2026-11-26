"""飞鸽单店只读循环：假页面、虚拟时钟与记录式 sleep、真事件总线。数据全部虚构。"""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from app.adapter.flybird.parse import ConvListResult, Message
from app.service.events import IM_UNREAD_CHANGED, IM_WAIT_CHANGED, EventBus
from app.service.im_session import ConvView, ImSession

START = datetime(2026, 12, 1, 2, 0, 0, tzinfo=UTC)
VERSION_LOW = ConvListResult(11001, {})


def msg(message_id, role="buyer", *, at=0, conv="1001", text="在吗") -> Message:
    """at：相对 START 的秒数。"""
    sent_at = (START + timedelta(seconds=at)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return Message(conv, message_id, role, text, sent_at)


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


class FakeTime:
    """虚拟时钟：sleep 记下时长并挂起，advance 按到期顺序逐个唤醒。"""

    def __init__(self) -> None:
        self.now = START
        self.slept: list[float] = []
        self._sleepers: list[tuple[datetime, asyncio.Future]] = []

    def clock(self) -> datetime:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        woken = asyncio.get_running_loop().create_future()
        self._sleepers.append((self.now + timedelta(seconds=seconds), woken))
        await woken

    async def advance(self, seconds: float) -> None:
        end = self.now + timedelta(seconds=seconds)
        await settle()
        while due := [s for s in self._sleepers if not s[1].done() and s[0] <= end]:
            self.now, woken = min(due, key=lambda s: s[0])
            woken.set_result(None)
            await settle()
        self.now = end


class FakeImPage:
    def __init__(self) -> None:
        self.closed = False
        self.reloads = 0
        self.reload_error: Exception | None = None

    async def reload(self) -> None:
        self.reloads += 1
        if self.reload_error is not None:
            raise self.reload_error


class Rig:
    def __init__(self, history=(), reload_history=None) -> None:
        self.time = FakeTime()
        self.page = FakeImPage()
        self.bus = EventBus()
        self.events: list[tuple[str, dict]] = []
        self.saved: list[list[Message]] = []
        self.reload_history = [] if reload_history is None else reload_history
        self.session = ImSession(
            1, self.page, self.bus, clock=self.time.clock, sleep=self.time.sleep,
            reload_history=self.reload_history, save_messages=self._save, history=list(history),
        )
        self.task: asyncio.Task

    async def _save(self, msgs: list[Message]) -> None:
        self.saved.append(list(msgs))

    def of(self, name: str) -> list[dict]:
        return [data for event, data in self.events if event == name]

    async def receive(self, *msgs: Message) -> None:
        self.session.on_messages(list(msgs))
        await settle()

    async def listed(self, result: ConvListResult) -> None:
        self.session.on_list(result)
        await settle()

    async def finish(self) -> str:
        reason = await asyncio.wait_for(self.task, 1)
        await settle()
        return reason


@asynccontextmanager
async def running(**kwargs):
    rig = Rig(**kwargs)
    async with rig.bus.subscribe() as sub:

        async def collect() -> None:
            async for event in sub:
                rig.events.append(event)

        collector = asyncio.create_task(collect())
        rig.task = asyncio.create_task(rig.session.run())
        await settle()
        try:
            yield rig
        finally:
            rig.session.stop()
            await rig.finish()
            collector.cancel()


def unread(count: int, new: int) -> dict:
    return {"shop_id": 1, "unread": count, "new": new}


def wait(waiting: int, overdue: int) -> dict:
    return {"shop_id": 1, "waiting": waiting, "overdue": overdue}


# ---- 基线与待回复 ----


async def test_history_is_baseline_no_event_new():
    async with running(history=[msg("msg-test-1"), msg("msg-test-2", at=1)]) as rig:
        assert rig.events[0] == (IM_UNREAD_CHANGED, unread(2, 0))
        assert rig.saved == []


async def test_buyer_messages_publish_new():
    async with running(history=[msg("msg-test-1"), msg("msg-test-2")]) as rig:
        await rig.receive(msg("msg-test-3"), msg("msg-test-4", conv="1002"))

        assert rig.of(IM_UNREAD_CHANGED)[-1] == unread(4, 2)


async def test_agent_reply_clears_pending_without_new():
    async with running(history=[msg("msg-test-1")]) as rig:
        await rig.receive(msg("msg-test-2", "agent", at=1))

        assert rig.of(IM_UNREAD_CHANGED)[-1] == unread(0, 0)


async def test_duplicate_message_ids_counted_once():
    async with running(history=[msg("msg-test-1")]) as rig:
        await rig.receive(msg("msg-test-1"), msg("msg-test-2"), msg("msg-test-2"))
        await rig.time.advance(30)
        await rig.receive(msg("msg-test-2"))
        await rig.time.advance(30)

        assert rig.of(IM_UNREAD_CHANGED) == [unread(1, 0), unread(2, 1)]
        assert rig.saved == [[msg("msg-test-2")]]


async def test_late_arrival_is_ordered_by_sent_time():
    async with running(history=[msg("msg-test-1", at=10)]) as rig:
        await rig.receive(msg("msg-test-2", "agent", at=5))

        assert rig.session.unread() == 1
        assert rig.session.snapshot()[0].last_role == "buyer"


async def test_snapshot_has_keys_pending_and_hides_text():
    history = [msg("msg-test-1", at=1), msg("msg-test-2", at=2, text="测试买家：在吗")]
    async with running(history=history) as rig:
        await rig.listed(ConvListResult(0, {"1001": "conv-test-1"}))
        await rig.receive(msg("msg-test-3", "agent", conv="1002"))

        first, second = sorted(rig.session.snapshot(), key=lambda v: v.conversation_id)
        assert first == ConvView(
            "1001", "conv-test-1", "测试买家：在吗", "buyer", "2026-12-01T02:00:02Z", 2,
            "2026-12-01T02:00:01Z",
        )
        assert (second.key, second.pending, second.waiting_since) == (None, 0, None)
        assert "在吗" not in repr(first)
        assert rig.page.reloads == 0


async def test_conversation_keeps_latest_50_messages():
    async with running() as rig:
        await rig.receive(*(msg(f"msg-test-{i}", at=i) for i in range(51)))

        assert rig.session.unread() == 50
        assert rig.session.snapshot()[0].waiting_since == "2026-12-01T02:00:01Z"


# ---- 去抖与保存 ----


async def test_burst_messages_leading_and_trailing_event():
    async with running() as rig:
        for i in range(5):
            await rig.receive(msg(f"msg-test-{i}"))
            await rig.time.advance(5)
        assert rig.of(IM_UNREAD_CHANGED) == [unread(0, 0), unread(1, 1)]
        await rig.time.advance(5)  # 距首次发布满 30 秒
        await rig.time.advance(60)

        assert rig.of(IM_UNREAD_CHANGED) == [unread(0, 0), unread(1, 1), unread(5, 4)]


async def test_message_without_count_change_does_not_delay_next_event():
    async with running() as rig:
        await rig.receive(msg("msg-test-1", "platform"))
        await rig.receive(msg("msg-test-2"))

        assert rig.of(IM_UNREAD_CHANGED)[-1] == unread(1, 1)


async def test_messages_saved():
    async with running() as rig:
        batch = [msg("msg-test-1"), msg("msg-test-2", "agent")]
        await rig.receive(*batch)

        assert rig.saved == [batch]


async def test_pending_messages_saved_and_counted_when_run_ends():
    async with running() as rig:
        await rig.receive(msg("msg-test-1"))
        rig.session.on_messages([msg("msg-test-2")])  # 仍在去抖间隔内
        rig.session.stop()

        assert await rig.finish() == "shutdown"
        assert rig.saved == [[msg("msg-test-1")], [msg("msg-test-2")]]
        assert rig.of(IM_UNREAD_CHANGED)[-1] == unread(2, 1)


# ---- 刷新与停止 ----


async def test_silence_reloads_after_poll_s():
    async with running() as rig:
        await rig.time.advance(299)
        assert rig.page.reloads == 0
        await rig.time.advance(1)

        assert rig.page.reloads == 1
        assert rig.reload_history == [START + timedelta(seconds=300)]
        assert max(rig.time.slept) <= 30


async def test_frames_prevent_silence_reload():
    async with running() as rig:
        for _ in range(10):
            await rig.time.advance(60)
            rig.session.on_frame(b"frame")

        assert rig.page.reloads == 0


async def test_still_silent_after_reload_returns_error():
    async with running() as rig:
        await rig.time.advance(600)

        assert await rig.finish() == "error"
        assert rig.page.reloads == 1


async def test_version_low_reloads_once_then_returns_version_low():
    async with running() as rig:
        await rig.listed(VERSION_LOW)
        assert rig.page.reloads == 1
        await rig.time.advance(60)
        assert not rig.task.done()
        await rig.listed(VERSION_LOW)

        assert await rig.finish() == "version_low"
        assert rig.page.reloads == 1


async def test_reload_respects_budget():
    full = [START - timedelta(hours=i) for i in range(1, 7)]
    async with running(reload_history=full) as rig:
        await rig.listed(VERSION_LOW)

        assert await rig.finish() == "version_low"
        assert rig.page.reloads == 0
        assert len(rig.reload_history) == 6


async def test_page_closed_returns_page_closed():
    async with running() as rig:
        rig.page.closed = True
        await rig.time.advance(30)

        assert await rig.finish() == "page_closed"


async def test_reload_failure_returns_error():
    async with running() as rig:
        rig.page.reload_error = RuntimeError("boom")
        await rig.listed(VERSION_LOW)

        assert await rig.finish() == "error"
        assert rig.of(IM_WAIT_CHANGED)[-1] == wait(0, 0)


async def test_reload_failure_on_closed_page_returns_page_closed():
    async with running() as rig:

        async def close_then_fail() -> None:
            rig.page.closed = True
            raise RuntimeError("boom")

        rig.page.reload = close_then_fail
        await rig.listed(VERSION_LOW)

        assert await rig.finish() == "page_closed"


# ---- 等待计时 ----


async def test_wait_tick_publishes_overdue_when_crossing_3_minutes():
    async with running() as rig:
        await rig.receive(msg("msg-test-1"))
        await rig.time.advance(180)
        assert rig.of(IM_WAIT_CHANGED) == [wait(0, 0), wait(1, 0)]
        await rig.time.advance(30)
        await rig.time.advance(30)

        assert rig.of(IM_WAIT_CHANGED) == [wait(0, 0), wait(1, 0), wait(1, 1)]


async def test_agent_reply_clears_wait():
    async with running(history=[msg("msg-test-1", at=-200)]) as rig:
        await rig.receive(msg("msg-test-2", "agent"))

        assert rig.of(IM_WAIT_CHANGED)[-1] == wait(0, 0)


async def test_history_seeds_wait_after_restart():
    async with running(history=[msg("msg-test-1", at=-200)]) as rig:
        assert rig.of(IM_WAIT_CHANGED) == [wait(1, 1)]


async def test_run_end_publishes_overdue_zero():
    async with running(history=[msg("msg-test-1", at=-200)]) as rig:
        rig.session.stop()
        await rig.finish()

        assert rig.of(IM_WAIT_CHANGED) == [wait(1, 1), wait(0, 0)]


async def test_cancelled_run_publishes_overdue_zero():
    rig = Rig(history=[msg("msg-test-1", at=-200)])
    async with rig.bus.subscribe() as sub:
        task = asyncio.create_task(rig.session.run())
        await settle()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        got = [await asyncio.wait_for(anext(sub), 1) for _ in range(3)]
    assert task.cancelled()
    assert got[-1] == (IM_WAIT_CHANGED, wait(0, 0))


async def test_event_payloads_have_counts_only():
    async with running(history=[msg("msg-test-1", at=-200, text="测试买家")]) as rig:
        await rig.listed(ConvListResult(0, {"1001": "conv-test-1"}))
        await rig.receive(msg("msg-test-2"))
        rig.session.stop()
        await rig.finish()

        keys = {IM_UNREAD_CHANGED: {"shop_id", "unread", "new"},
                IM_WAIT_CHANGED: {"shop_id", "waiting", "overdue"}}
        assert {event for event, _ in rig.events} == set(keys)
        for event, data in rig.events:
            assert set(data) == keys[event]
            assert all(type(value) is int for value in data.values())
        for private in ("测试买家", "在吗", "conv-test-1", "msg-test"):
            assert private not in str(rig.events)
