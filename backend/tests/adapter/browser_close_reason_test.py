"""持有方经 on_close 得知浏览器为何被关：退出、过期、进程已不在、让出、后端退出。"""

import asyncio

import pytest

from app.adapter.browser.browser_registry import BrowserRegistry, CloseReason, Purpose
from app.adapter.browser.cloak_launch import CloakUnavailable
from tests.adapter.browser_registry_test import Clock, FakeProcs, launcher


@pytest.fixture
def env(tmp_path):
    profiles = tmp_path / "profiles"
    (profiles / "1").mkdir(parents=True)
    procs, clock = FakeProcs(), Clock()
    reg = BrowserRegistry(procs, clock=clock, close_timeout_s=0.05)
    return reg, procs, clock, profiles


def _open(reg, procs, profiles, reasons, purpose=Purpose.IM):
    return reg.open(profiles / "1", purpose, launcher(procs, profiles / "1", 100),
                    on_close=reasons.append)


async def test_done_when_holder_exits(env):
    reg, procs, _, profiles = env
    reasons: list[str] = []
    async with _open(reg, procs, profiles, reasons):
        assert reasons == []
    assert reasons == [CloseReason.DONE]


async def test_expired_by_sweep(env):
    reg, procs, clock, profiles = env
    reasons: list[str] = []
    async with _open(reg, procs, profiles, reasons):
        clock.t += 24 * 3600 + 1
        await reg.sweep(profiles)
        assert reasons == ["expired"]
    assert reasons == ["expired"]  # 持有方退出不再重复回调


async def test_process_gone(env):
    reg, procs, _, profiles = env
    reasons: list[str] = []
    async with _open(reg, procs, profiles, reasons):
        procs.browsers.clear()
        await reg.sweep(profiles)
    assert reasons == ["process_gone"]


async def test_preempted_by_close_shop(env):
    reg, procs, _, profiles = env
    reasons: list[str] = []
    async with _open(reg, procs, profiles, reasons):
        assert await reg.close_shop(1)
    assert reasons == ["preempted"]


async def test_shutdown_by_close_all(env):
    reg, procs, _, profiles = env
    reasons: list[str] = []
    async with _open(reg, procs, profiles, reasons):
        await reg.close_all()
    assert reasons == ["shutdown"]


async def test_custom_reason_passes_through(env):
    reg, procs, _, profiles = env
    reasons: list[str] = []
    async with _open(reg, procs, profiles, reasons):
        await reg.close_shop(1, "login_requested")
    assert reasons == ["login_requested"]


async def test_reason_reported_even_when_close_times_out(env):
    reg, procs, _, profiles = env
    reasons: list[str] = []
    launch = launcher(procs, profiles / "1", 100, hang=True)
    async with reg.open(profiles / "1", Purpose.IM, launch, on_close=reasons.append):
        await reg.close_shop(1)
    assert reasons == ["preempted"] and procs.killed == [100]


async def test_not_called_when_launch_fails(env):
    reg, _, _, profiles = env
    reasons: list[str] = []

    async def boom():
        raise CloakUnavailable("x")

    with pytest.raises(CloakUnavailable):
        async with reg.open(profiles / "1", Purpose.IM, boom, on_close=reasons.append):
            pass
    assert reasons == []


async def test_callback_error_does_not_block_unregister(env):
    reg, procs, _, profiles = env

    def bad(_reason: str) -> None:
        raise RuntimeError("holder bug")

    async with reg.open(profiles / "1", Purpose.IM, launcher(procs, profiles / "1", 100),
                        on_close=bad):
        pass
    assert reg.list() == []


async def test_registry_is_free_when_callback_runs(env):
    """回调里能看到目录已注销，持有方可以直接重新打开（im 每日重启）。"""
    reg, procs, clock, profiles = env
    seen: list[int] = []
    async with reg.open(profiles / "1", Purpose.IM, launcher(procs, profiles / "1", 100),
                        on_close=lambda _r: seen.append(len(reg.list()))):
        clock.t += 24 * 3600 + 1
        await reg.sweep(profiles)
        await asyncio.sleep(0)
    assert seen == [0]
