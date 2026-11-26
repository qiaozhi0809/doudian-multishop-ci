"""飞鸽常驻页的退避、每日启动上限与手动重连：不出现快速重连循环。"""

import asyncio
from datetime import timedelta

import pytest

from app.adapter.browser.cloak_launch import PROFILE_IN_USE, CloakUnavailable
from app.adapter.flybird.parse import ConvListResult
from app.service.events import SHOP_STATUS_CHANGED
from tests.service.im_watcher_support import ADMIN, Rig, drain, until

VERSION_LOW = ConvListResult(11001, {})


@pytest.fixture
async def rig(engine, tmp_path):
    rig = Rig(engine, tmp_path)
    yield rig
    await rig.watcher.shutdown()


async def fail_next_retry(rig: Rig, seconds: float) -> None:
    """睡到下一次重试并等它失败。"""
    attempts = len(rig.registry.opened)
    await rig.advance(seconds)
    await until(lambda: len(rig.registry.opened) == attempts + 1 and rig.state() == "backoff")


async def test_backoff_on_error_no_fast_loop(rig):
    rig.registry.launch_error = CloakUnavailable(PROFILE_IN_USE)
    await rig.start(wait="backoff")

    await rig.advance(59)
    assert len(rig.registry.opened) == 1
    await fail_next_retry(rig, 1)
    await rig.advance(119)
    assert len(rig.registry.opened) == 2
    await fail_next_retry(rig, 1)

    assert rig.time.slept == [60, 120, 240]


async def test_stable_run_resets_backoff(rig):
    rig.registry.launch_error = CloakUnavailable(PROFILE_IN_USE)
    await rig.start(wait="backoff")
    await fail_next_retry(rig, 60)
    rig.registry.launch_error = None
    await rig.advance(120)
    await rig.wait_state("running")

    rig.time.now += timedelta(hours=1)
    await rig.registry.close_shop(rig.shop_id, "process_gone")
    await rig.wait_state("backoff")

    assert rig.watcher.status(rig.shop_id).next_retry_at == "2026-12-01T03:04:00Z"


async def test_short_run_keeps_backoff_growing(rig):
    await rig.start()
    for delay in (60, 120):
        await rig.registry.close_shop(rig.shop_id, "process_gone")
        await rig.wait_state("backoff")
        await rig.advance(delay)
        await rig.wait_state("running")

    assert [s for s in rig.time.slept if s >= 60] == [60, 120]


async def version_low_round(rig: Rig) -> None:
    """当前页面报版本过低：能刷新就刷新一次，刷新后仍过低，会话结束。"""
    page = rig.attach.pages[-1]
    page.on_list(VERSION_LOW)
    await drain()
    if rig.state() == "running":
        page.on_list(VERSION_LOW)


async def test_version_low_repeated_sets_needs_refresh_and_stops_retrying(rig):
    rig.attach.during = lambda page: page.on_list(VERSION_LOW)
    await rig.watcher.start(rig.shop_id, actor=ADMIN)
    await until(lambda: rig.attach.pages and rig.attach.pages[0].reloads == 1)
    await version_low_round(rig)

    await rig.wait_state("backoff")
    assert rig.stopped_events() == []
    await rig.advance(60)
    await until(lambda: len(rig.attach.pages) == 2 and rig.state() == "backoff")
    await rig.advance(120)
    await rig.wait_state("needs_refresh")
    await rig.advance(86400)

    assert len(rig.registry.opened) == 3
    assert [p.reloads for p in rig.attach.pages] == [1, 0, 0]  # 刷新限额跨会话累计
    assert rig.stopped_events() == [{"shop_id": rig.shop_id, "state": "needs_refresh"}]
    assert rig.watcher.status(rig.shop_id).next_retry_at is None
    assert rig.registry.open_contexts() == []


async def _reach_needs_refresh(rig: Rig) -> None:
    rig.attach.during = lambda page: page.on_list(VERSION_LOW)
    await rig.watcher.start(rig.shop_id, actor=ADMIN)
    await until(lambda: rig.attach.pages and rig.attach.pages[0].reloads == 1)
    await version_low_round(rig)
    for pages, delay in ((2, 60), (3, 120)):
        await rig.wait_state("backoff")
        await rig.advance(delay)
        await until(lambda n=pages: len(rig.attach.pages) == n)
    await rig.wait_state("needs_refresh")


async def test_status_event_does_not_restart_needs_refresh(rig):
    stop = asyncio.Event()
    task = asyncio.create_task(rig.watcher.run(rig.events, stop))
    await rig.wait_state("running")
    for delay in (60, 120):
        await version_low_round(rig)
        await rig.wait_state("backoff")
        await rig.advance(delay)
        await rig.wait_state("running")
    await version_low_round(rig)
    await rig.wait_state("needs_refresh")

    rig.events.publish(SHOP_STATUS_CHANGED, {"shop_id": rig.shop_id})
    await drain()

    assert rig.state() == "needs_refresh"
    assert len(rig.registry.opened) == 3
    stop.set()
    await asyncio.wait_for(task, 1)


async def test_restart_resets_backoff_and_goes_through_gates(rig):
    await _reach_needs_refresh(rig)
    rig.attach.during = None
    ready_before = len(rig.env.egress.ready_calls)

    await rig.watcher.restart(rig.shop_id, actor=ADMIN)
    await rig.wait_state("running")

    assert len(rig.env.egress.ready_calls) == ready_before + 1
    await rig.registry.close_shop(rig.shop_id, "process_gone")
    await rig.wait_state("backoff")
    assert rig.time.slept[-1] == 60


async def test_restart_running_shop_reopens_page(rig):
    await rig.start()

    await rig.watcher.restart(rig.shop_id, actor=ADMIN)
    await rig.wait_state("running")

    assert [c.context.closed for c in rig.registry.opened] == [True, False]
    assert rig.audits("im.stop")[0]["actor"] == ADMIN


async def test_restart_blocked_shop_opens_nothing(rig):
    rig.pause(rig.shop_id)

    status = await rig.watcher.restart(rig.shop_id, actor=ADMIN)
    await drain()

    assert status.state == "stopped"
    assert rig.registry.opened == []


async def test_start_limit_per_day(rig):
    await rig.start()
    for _ in range(23):  # 每日重启走 0 秒退避，仍计入当天启动次数
        attempts = len(rig.registry.opened)
        await rig.registry.close_shop(rig.shop_id, "expired")
        await rig.wait_state("backoff")
        await rig.advance(0)
        await until(lambda n=attempts: len(rig.registry.opened) == n + 1)
        await rig.wait_state("running")
    assert len(rig.registry.opened) == 24

    await rig.registry.close_shop(rig.shop_id, "expired")
    await rig.wait_state("backoff")
    await rig.advance(0)
    await until(lambda: rig.watcher.status(rig.shop_id).next_retry_at == "2026-12-02T02:00:00Z")
    await rig.advance(3600)

    assert len(rig.registry.opened) == 24
    assert rig.state() == "backoff"
    assert rig.watcher.status(rig.shop_id).last_error == "今日启动次数已达上限"

    await rig.advance(86400 - 3600)  # 最早那次启动满一天后恢复
    await rig.wait_state("running")
    assert len(rig.registry.opened) == 25


async def test_daily_limit_survives_manual_restart(rig):
    await rig.start()
    for _ in range(23):
        attempts = len(rig.registry.opened)
        await rig.watcher.restart(rig.shop_id, actor=ADMIN)
        await until(lambda n=attempts: len(rig.registry.opened) == n + 1)
        await rig.wait_state("running")

    await rig.watcher.restart(rig.shop_id, actor=ADMIN)
    await rig.wait_state("backoff")

    assert len(rig.registry.opened) == 24
