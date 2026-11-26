"""飞鸽常驻页生命周期：选店、关卡、名额、状态事件、让出、消息存库、审计与关机。"""

import asyncio

import pytest

from app.adapter.browser.browser_registry import Purpose
from app.adapter.browser.cloak_launch import PROFILE_IN_USE, CloakUnavailable
from app.adapter.browser.login import playwright_proxy
from app.adapter.doudian.errors import EgressUnavailable
from app.service.events import SHOP_STATUS_CHANGED
from tests.service.im_watcher_support import ADMIN, IM_PROXY, Rig, drain, until


@pytest.fixture
async def rig(engine, tmp_path):
    rig = Rig(engine, tmp_path)
    yield rig
    await rig.watcher.shutdown()


@pytest.fixture
async def watching(rig):
    """跑着订阅循环的 watcher。"""
    stop = asyncio.Event()
    task = asyncio.create_task(rig.watcher.run(rig.events, stop))
    await until(lambda: rig.events.subscriber_count)
    yield rig
    stop.set()
    await asyncio.wait_for(task, 1)


def changed(rig: Rig, shop_id: int | None = None) -> None:
    rig.events.publish(SHOP_STATUS_CHANGED, {"shop_id": shop_id or rig.shop_id})


# ---- 启动与关卡 ----


async def test_launch_via_registry_purpose_im_offscreen(rig):
    await rig.start()

    call = rig.registry.opened[0]
    assert call.profile_dir == rig.profiles / str(rig.shop_id)
    assert call.purpose is Purpose.IM
    assert call.proxy == playwright_proxy(IM_PROXY)
    assert call.kwargs["offscreen"] is True
    assert "max_age_s" not in call.kwargs
    assert [info.purpose for info in rig.registry.list()] == [Purpose.IM]
    assert rig.watcher.page(rig.shop_id) is rig.attach.pages[0]
    assert rig.watcher.status(rig.shop_id).last_error is None


async def test_start_passes_offscreen_false_through(rig):
    await rig.watcher.start(rig.shop_id, actor=ADMIN, offscreen=False)
    await rig.wait_state("running")

    assert rig.registry.opened[0].kwargs["offscreen"] is False


async def test_selects_active_enabled_shops_only(rig):
    browser_channel = rig.add_shop()
    rig.update(browser_channel, channel="browser")
    off = rig.add_shop(enabled=False)
    needs_login = rig.add_shop()
    rig.set_status(needs_login, "needs_login")
    paused = rig.add_shop()
    rig.pause(paused)

    assert rig.watcher.im_shop_ids() == [rig.shop_id, browser_channel]
    assert off not in rig.watcher.im_shop_ids()


async def test_run_starts_selected_shops(rig):
    other = rig.add_shop()
    rig.add_shop(enabled=False)
    stop = asyncio.Event()
    task = asyncio.create_task(rig.watcher.run(rig.events, stop))

    await rig.wait_state("running")
    await rig.wait_state("running", other)
    assert len(rig.registry.opened) == 2

    stop.set()
    await asyncio.wait_for(task, 1)


async def test_run_clears_stale_wait_state_for_every_shop(rig):
    off = rig.add_shop(enabled=False)
    stop = asyncio.Event()
    task = asyncio.create_task(rig.watcher.run(rig.events, stop))
    await rig.wait_state("running")

    cleared = [{"shop_id": s, "waiting": 0, "overdue": 0} for s in (rig.shop_id, off)]
    assert rig.wait_events()[:2] == cleared

    stop.set()
    await asyncio.wait_for(task, 1)


async def test_paused_shop_never_opens_browser(rig):
    rig.pause(rig.shop_id)

    await rig.watcher.start(rig.shop_id, actor=ADMIN)
    await drain()

    assert rig.registry.opened == []
    assert rig.state() == "stopped"
    assert rig.env.egress.ready_calls == []


async def test_switch_off_shop_start_is_off(rig):
    rig.update(rig.shop_id, im_enabled=0)

    status = await rig.watcher.start(rig.shop_id, actor=ADMIN)
    await drain()

    assert status.state == "off"
    assert rig.registry.opened == []


async def test_precheck_failure_opens_no_browser(rig):
    rig.env.egress.error = EgressUnavailable("出口不可达")

    await rig.start(wait="backoff")

    assert rig.registry.opened == []
    assert rig.watcher.status(rig.shop_id).last_error == "EgressUnavailable"


async def test_proxy_none_on_proxy_mode_refused(rig):
    rig.set_egress(rig.shop_id, egress_mode="proxy")
    rig.env.egress.proxy = None

    await rig.start(wait="backoff")

    assert rig.registry.opened == []
    assert rig.watcher.status(rig.shop_id).last_error == "EgressUnavailable"
    assert rig.env.egress.unreachable_marks == [rig.shop_id]


async def test_direct_mode_opens_without_proxy(rig):
    rig.set_egress(rig.shop_id, egress_mode="direct")
    rig.env.egress.proxy = None

    await rig.start()

    assert rig.registry.opened[0].proxy is None


async def test_registry_cloak_unavailable_recorded(rig):
    rig.registry.launch_error = CloakUnavailable(PROFILE_IN_USE)

    await rig.start(wait="backoff")

    status = rig.watcher.status(rig.shop_id)
    assert status.last_error == PROFILE_IN_USE
    assert status.next_retry_at == "2026-12-01T02:01:00Z"
    assert rig.time.slept == [60]


async def test_start_waits_for_shop_queue(rig):
    release = asyncio.Event()
    busy = asyncio.create_task(
        rig.env.runner.run(rig.shop_id, lambda _c: release.wait(), actor=ADMIN))
    await drain()

    await rig.watcher.start(rig.shop_id, actor=ADMIN)
    await drain()
    assert rig.registry.opened == []
    assert rig.state() == "starting"

    release.set()
    await busy
    await rig.wait_state("running")


async def test_switch_off_while_queued_in_shop_queue_opens_nothing(rig):
    release = asyncio.Event()
    busy = asyncio.create_task(
        rig.env.runner.run(rig.shop_id, lambda _c: release.wait(), actor=ADMIN))
    await drain()
    await rig.watcher.start(rig.shop_id, actor=ADMIN)
    await drain()

    rig.update(rig.shop_id, im_enabled=0)
    release.set()
    await busy

    await rig.wait_state("off")
    assert rig.registry.opened == []


async def test_global_cap_limits_open_pages(engine, tmp_path):
    rig = Rig(engine, tmp_path, max_browsers=2)
    shops = [rig.shop_id, rig.add_shop(), rig.add_shop()]
    for shop_id in shops:
        await rig.watcher.start(shop_id, actor=ADMIN)
    await rig.wait_state("running", shops[0])
    await rig.wait_state("running", shops[1])
    await drain()

    assert rig.state(shops[2]) == "queued"
    assert len(rig.registry.open_contexts()) == 2

    await rig.watcher.stop(shops[0], reason="ineligible", actor=ADMIN)
    await rig.wait_state("running", shops[2])
    assert len(rig.registry.open_contexts()) == 2
    await rig.watcher.shutdown()


async def test_stop_while_queued_gives_up_place(engine, tmp_path):
    rig = Rig(engine, tmp_path, max_browsers=1)
    second, third = rig.add_shop(), rig.add_shop()
    await rig.start()
    await rig.watcher.start(second, actor=ADMIN)
    await rig.watcher.start(third, actor=ADMIN)
    await drain()

    await rig.watcher.stop(second, reason="ineligible", actor=ADMIN)
    assert rig.state(second) == "stopped"
    await rig.watcher.stop(rig.shop_id, reason="ineligible", actor=ADMIN)

    await rig.wait_state("running", third)
    assert len(rig.registry.opened) == 2
    await rig.watcher.shutdown()


async def test_second_start_while_running_is_noop(rig):
    await rig.start()

    status = await rig.watcher.start(rig.shop_id, actor=ADMIN)
    await drain()

    assert status.state == "running"
    assert len(rig.registry.opened) == 1


# ---- 状态事件 ----


async def test_status_changed_needs_login_stops_page(watching):
    await watching.wait_state("running")

    watching.set_status(watching.shop_id, "needs_login")
    changed(watching)

    await watching.wait_state("stopped")
    assert watching.registry.open_contexts() == []
    assert watching.audits("im.stop")[0]["resp"]["reason"] == "ineligible"
    assert watching.stopped_events() == []


async def test_status_changed_egress_bad_stops_page(watching):
    await watching.wait_state("running")

    watching.set_egress(watching.shop_id, egress_status="changed")
    changed(watching)

    await watching.wait_state("stopped")
    assert watching.registry.open_contexts() == []


async def test_switch_off_stops_page(watching):
    await watching.wait_state("running")

    watching.update(watching.shop_id, im_enabled=0)
    changed(watching)

    await watching.wait_state("off")
    assert watching.registry.open_contexts() == []
    await watching.advance(7200)
    assert len(watching.registry.opened) == 1


async def test_status_changed_back_to_ok_starts_again(watching):
    await watching.wait_state("running")
    watching.set_status(watching.shop_id, "needs_login")
    changed(watching)
    await watching.wait_state("stopped")

    watching.set_status(watching.shop_id, "active")
    changed(watching)

    await watching.wait_state("running")
    assert len(watching.registry.opened) == 2


async def test_status_changed_does_not_cut_backoff_short(watching):
    await watching.wait_state("running")
    watching.registry.launch_error = CloakUnavailable(PROFILE_IN_USE)
    await watching.registry.close_shop(watching.shop_id, "process_gone")
    await watching.wait_state("backoff")

    for _ in range(5):  # 出口复查也会发状态事件
        changed(watching)
    await drain()

    assert watching.state() == "backoff"
    assert len(watching.registry.opened) == 1


async def test_status_changed_while_blocked_cancels_pending_retry(watching):
    await watching.wait_state("running")
    await watching.registry.close_shop(watching.shop_id, "process_gone")
    await watching.wait_state("backoff")

    watching.pause(watching.shop_id)
    changed(watching)
    await watching.wait_state("stopped")
    await watching.advance(7200)

    assert len(watching.registry.opened) == 1
    assert watching.watcher.status(watching.shop_id).next_retry_at is None


# ---- 查询 ----


async def test_statuses_lists_tracked_shops(rig):
    other = rig.add_shop()
    await rig.start()
    await rig.start(other)

    assert {(s.shop_id, s.state) for s in rig.watcher.statuses()} == {
        (rig.shop_id, "running"), (other, "running")}
    assert rig.watcher.snapshot(999) == []
    assert rig.watcher.page(999) is None


async def test_status_of_untracked_shop_follows_gates(rig):
    assert rig.state() == "stopped"
    rig.update(rig.shop_id, im_enabled=0)
    assert rig.state() == "off"
