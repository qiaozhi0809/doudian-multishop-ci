"""飞鸽常驻页的结束：让出资料目录、停止原因判定、手动停止与关机。"""

import asyncio

import pytest

from app.adapter.browser.cloak_launch import PROFILE_IN_USE, CloakUnavailable
from tests.service.im_watcher_support import ADMIN, Rig, drain, until


@pytest.fixture
async def rig(engine, tmp_path):
    rig = Rig(engine, tmp_path)
    yield rig
    await rig.watcher.shutdown()


# ---- 让出 ----


async def test_yield_profile_closes_shop_and_waits(rig):
    await rig.start()

    assert await rig.watcher.yield_profile(rig.shop_id) is True

    assert rig.registry.closed_shops == [(rig.shop_id, "preempted")]
    assert rig.registry.list() == []
    assert rig.audits("im.stop")[0]["resp"]["reason"] == "preempted"  # 返回前会话已结束
    assert rig.watcher.page(rig.shop_id) is None


async def test_yield_profile_without_page_does_nothing(rig):
    assert await rig.watcher.yield_profile(rig.shop_id) is False
    rig.registry.launch_error = CloakUnavailable(PROFILE_IN_USE)
    await rig.start(wait="backoff")

    assert await rig.watcher.yield_profile(rig.shop_id) is False
    assert rig.registry.closed_shops == []


async def test_yield_from_shop_queue_does_not_deadlock(rig):
    await rig.start()

    async def scan(_client) -> bool:
        return await rig.watcher.yield_profile(rig.shop_id)

    assert await asyncio.wait_for(rig.env.runner.run(rig.shop_id, scan, actor=ADMIN), 2) is True


async def test_preempted_restarts_after_60s_through_gates(rig):
    await rig.start()
    ready_before = len(rig.env.egress.ready_calls)
    await rig.watcher.yield_profile(rig.shop_id)
    await rig.wait_state("backoff")

    await rig.advance(59)
    assert len(rig.registry.opened) == 1

    await rig.advance(1)
    await rig.wait_state("running")
    assert len(rig.registry.opened) == 2
    assert len(rig.env.egress.ready_calls) == ready_before + 1


# ---- 停止原因 ----


@pytest.mark.parametrize(("close_reason", "stop_reason"), [
    ("expired", "lifetime"),
    ("preempted", "preempted"),
    ("shutdown", "shutdown"),
    ("process_gone", "page_closed"),
])
async def test_close_reason_maps_to_stop_reason(rig, close_reason, stop_reason):
    await rig.start()

    await rig.registry.close_shop(rig.shop_id, close_reason)

    await until(lambda: rig.audits("im.stop"))
    assert rig.audits("im.stop")[0]["resp"]["reason"] == stop_reason


async def test_page_closing_by_itself_is_page_closed(rig):
    await rig.start()

    await rig.attach.pages[0].context.close()
    await rig.advance(30)  # 会话下一次唤醒才发现

    await rig.wait_state("backoff")
    assert rig.audits("im.stop")[0]["resp"]["reason"] == "page_closed"
    assert rig.registry.list() == []


async def test_lifetime_end_restarts_through_gates(rig):
    await rig.start()
    ready_before = len(rig.env.egress.ready_calls)

    await rig.registry.close_shop(rig.shop_id, "expired")
    await until(lambda: rig.state() == "backoff")
    await rig.advance(0)

    await rig.wait_state("running")
    assert len(rig.registry.opened) == 2
    assert len(rig.env.egress.ready_calls) == ready_before + 1
    assert rig.time.slept.count(0) == 1


# ---- 关机 ----


async def test_shutdown_exits_all_contexts(rig):
    other = rig.add_shop()
    await rig.start()
    await rig.start(other)

    await asyncio.wait_for(rig.watcher.shutdown(), 2)

    assert rig.registry.open_contexts() == []
    assert rig.registry.list() == []
    assert rig.state() == rig.state(other) == "stopped"
    assert [r["resp"]["reason"] for r in rig.audits("im.stop")] == ["shutdown", "shutdown"]
    assert rig.stopped_events() == []
    assert (await rig.watcher.start(rig.shop_id, actor=ADMIN)).state == "stopped"
    await drain()
    assert len(rig.registry.opened) == 2


async def test_shutdown_cancels_pending_retry_and_hung_launch(rig, monkeypatch):
    monkeypatch.setattr("app.service.im_watcher.SHUTDOWN_WAIT_S", 0.05)
    other = rig.add_shop()
    rig.registry.launch_error = CloakUnavailable(PROFILE_IN_USE)
    await rig.start(wait="backoff")
    rig.registry.launch_error = None
    rig.attach.gate = asyncio.Event()  # 页面一直打不开
    await rig.watcher.start(other, actor=ADMIN)
    await until(lambda: rig.registry.open_contexts())

    await asyncio.wait_for(rig.watcher.shutdown(), 2)
    await rig.advance(7200)

    assert rig.registry.open_contexts() == []
    assert len(rig.registry.opened) == 2
    assert rig.state() == rig.state(other) == "stopped"


async def test_stop_while_browser_launching_never_opens_workspace(rig):
    rig.registry.launch_gate = asyncio.Event()
    await rig.watcher.start(rig.shop_id, actor=ADMIN)
    await until(lambda: rig.registry.opened)

    rig.pause(rig.shop_id)  # 风控暂停：浏览器起来了也不能再访问抖店
    stopping = asyncio.create_task(
        rig.watcher.stop(rig.shop_id, reason="ineligible", actor=ADMIN))
    await drain()
    rig.registry.launch_gate.set()
    await asyncio.wait_for(stopping, 2)

    assert rig.attach.pages == []
    assert rig.registry.open_contexts() == []


async def test_stop_during_launch_closes_page_without_running(rig):
    rig.attach.gate = asyncio.Event()
    await rig.watcher.start(rig.shop_id, actor=ADMIN)
    await until(lambda: rig.registry.open_contexts())

    stopping = asyncio.create_task(
        rig.watcher.stop(rig.shop_id, reason="ineligible", actor=ADMIN))
    await drain()
    rig.attach.gate.set()
    await asyncio.wait_for(stopping, 2)

    assert rig.registry.open_contexts() == []
    assert rig.state() == "stopped"
    await rig.advance(7200)
    assert len(rig.registry.opened) == 1
