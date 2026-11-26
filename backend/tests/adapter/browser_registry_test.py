"""浏览器登记：登记/注销、关闭超时强杀、巡检（过期、进程已不在、孤儿）、启动清理。

全部用假进程表与假上下文，不真的起浏览器。
"""

import asyncio
from pathlib import Path

import pytest
from structlog.testing import capture_logs

from app.adapter.browser.browser_process import SINGLETON_FILES, BrowserProc
from app.adapter.browser.browser_registry import (
    MAX_AGE_S,
    BrowserRegistry,
    Purpose,
)
from app.adapter.browser.cloak_launch import PROFILE_IN_USE, CloakUnavailable


class FakeProcs:
    """进程表：pid → --user-data-dir。kill_tree 直接从表里移除。"""

    def __init__(self) -> None:
        self.browsers: dict[int, str] = {}
        self.killed: list[int] = []

    def list_browsers(self) -> list[BrowserProc]:
        return [BrowserProc(pid, d) for pid, d in self.browsers.items()]

    def alive(self, pid: int) -> bool:
        return pid in self.browsers

    def kill_tree(self, pid: int) -> None:
        self.killed.append(pid)
        self.browsers.pop(pid, None)


class FakeCtx:
    def __init__(self, procs: FakeProcs, pid: int, *, hang: bool = False,
                 leave_running: bool = False) -> None:
        self.procs, self.pid, self.hang, self.leave_running = procs, pid, hang, leave_running
        self.close_calls = 0

    async def close(self) -> None:
        self.close_calls += 1
        if self.hang and self.close_calls == 1:
            await asyncio.sleep(3600)
        if not self.leave_running:
            self.procs.browsers.pop(self.pid, None)


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def profiles(tmp_path: Path) -> Path:
    p = tmp_path / "profiles"
    for sid in ("1", "2", "3"):
        (p / sid).mkdir(parents=True)
    return p


@pytest.fixture
def procs() -> FakeProcs:
    return FakeProcs()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def reg(procs: FakeProcs, clock: Clock) -> BrowserRegistry:
    return BrowserRegistry(procs, clock=clock, close_timeout_s=0.05)


def launcher(procs: FakeProcs, profile: Path, pid: int, **ctx_kw):
    ctxs: list[FakeCtx] = []

    async def launch() -> FakeCtx:
        procs.browsers[pid] = str(profile)
        ctx = FakeCtx(procs, pid, **ctx_kw)
        ctxs.append(ctx)
        return ctx

    launch.ctxs = ctxs  # type: ignore[attr-defined]
    return launch


def _locks(d: Path) -> None:
    for name in SINGLETON_FILES:
        (d / name).write_text("x")


async def test_open_registers_and_close_unregisters(reg, procs, profiles):
    launch = launcher(procs, profiles / "1", 100)
    async with reg.open(profiles / "1", Purpose.LOGIN, launch) as ctx:
        [info] = reg.list()
        assert (info.shop_id, info.purpose, info.pid) == (1, Purpose.LOGIN, 100)
        assert info.max_age_s == MAX_AGE_S[Purpose.LOGIN] == 600
        assert info.started_at.tzinfo is not None
    assert reg.list() == []
    assert ctx.close_calls == 1 and procs.killed == []


def test_max_ages():
    assert MAX_AGE_S[Purpose.SCRAPE] == 120
    assert MAX_AGE_S[Purpose.IM] == 24 * 3600


async def test_close_timeout_kills_process_tree(reg, procs, profiles):
    launch = launcher(procs, profiles / "1", 100, hang=True)
    with capture_logs() as logs:
        async with reg.open(profiles / "1", Purpose.SCRAPE, launch):
            pass
    assert procs.killed == [100] and reg.list() == []
    closed = [e for e in logs if e["event"] == "browser.closed"]
    assert closed and closed[0]["killed"] is True and closed[0]["shop_id"] == 1


async def test_graceful_close_leaving_process_alive_is_killed(reg, procs, profiles):
    launch = launcher(procs, profiles / "1", 100, leave_running=True)
    async with reg.open(profiles / "1", Purpose.LOGIN, launch):
        pass
    assert procs.killed == [100]


async def test_same_profile_twice_is_refused_without_launching(reg, procs, profiles):
    first = launcher(procs, profiles / "1", 100)
    second = launcher(procs, profiles / "1", 101)
    async with reg.open(profiles / "1", Purpose.IM, first):
        with pytest.raises(CloakUnavailable, match=PROFILE_IN_USE):
            async with reg.open(profiles / "1", Purpose.LOGIN, second):
                pass
    assert second.ctxs == []


async def test_launch_failure_leaves_no_entry(reg, profiles):
    async def boom():
        raise CloakUnavailable("x")

    with pytest.raises(CloakUnavailable):
        async with reg.open(profiles / "1", Purpose.LOGIN, boom):
            pass
    assert reg.list() == []


async def test_sweep_closes_expired_and_keeps_fresh(reg, procs, profiles, clock):
    old = launcher(procs, profiles / "1", 100)
    fresh = launcher(procs, profiles / "2", 200)
    async with reg.open(profiles / "1", Purpose.SCRAPE, old) as c1:
        clock.t += 100
        async with reg.open(profiles / "2", Purpose.LOGIN, fresh) as c2:
            clock.t += 30  # scrape 已 130 秒 > 120；login 才 30 秒
            with capture_logs() as logs:
                await reg.sweep(profiles)
            assert [i.shop_id for i in reg.list()] == [2]
            assert c1.close_calls == 1 and c2.close_calls == 0
            assert any(e["event"] == "browser.closed" and e["reason"] == "expired"
                       and e["purpose"] == "scrape" for e in logs)
    # 持有方退出时再关一次不报错
    assert c1.close_calls == 1 and reg.list() == []


async def test_im_is_restarted_daily(reg, procs, profiles, clock):
    launch = launcher(procs, profiles / "1", 100)
    async with reg.open(profiles / "1", Purpose.IM, launch) as ctx:
        clock.t += 23 * 3600
        await reg.sweep(profiles)
        assert len(reg.list()) == 1
        clock.t += 3600 + 1
        await reg.sweep(profiles)
        assert reg.list() == [] and ctx.close_calls == 1


async def test_sweep_drops_entries_whose_process_is_gone(reg, procs, profiles):
    launch = launcher(procs, profiles / "1", 100)
    async with reg.open(profiles / "1", Purpose.LOGIN, launch):
        procs.browsers.clear()  # 用户关了窗口 / 浏览器崩溃
        with capture_logs() as logs:
            await reg.sweep(profiles)
        assert reg.list() == []
        assert any(e.get("reason") == "process_gone" for e in logs)


async def test_sweep_kills_orphans_under_profiles_only(reg, procs, profiles, tmp_path):
    launch = launcher(procs, profiles / "1", 100)
    procs.browsers[300] = str(profiles / "3")  # 孤儿：属于 profiles 但未登记
    procs.browsers[900] = str(tmp_path / "chrome-user")  # 用户自己的 Chrome
    _locks(profiles / "3")
    async with reg.open(profiles / "1", Purpose.LOGIN, launch):
        with capture_logs() as logs:
            await reg.sweep(profiles)
    assert procs.killed == [300]
    assert 900 in procs.browsers
    assert not any((profiles / "3" / n).exists() for n in SINGLETON_FILES)
    orphan = [e for e in logs if e["event"] == "browser.orphan_killed"]
    assert orphan == [{"event": "browser.orphan_killed", "shop_id": 3, "reason": "orphan",
                       "log_level": "warning"}]


async def test_sweep_spares_browser_still_launching(reg, procs, profiles):
    gate = asyncio.Event()

    async def slow_launch():
        procs.browsers[100] = str(profiles / "1")  # 进程已出现，launch 还没返回
        await gate.wait()
        return FakeCtx(procs, 100)

    async def hold():
        async with reg.open(profiles / "1", Purpose.LOGIN, slow_launch):
            pass

    task = asyncio.create_task(hold())
    await asyncio.sleep(0)
    await reg.sweep(profiles)
    assert procs.killed == []
    gate.set()
    await task


async def test_startup_cleanup_kills_orphans_and_clears_stale_locks(reg, procs, profiles):
    procs.browsers[100] = str(profiles / "1" / "Default")
    _locks(profiles / "1")
    _locks(profiles / "2")  # 进程早已不在，只剩锁文件
    (profiles / "2" / "Cookies").write_text("keep")
    await reg.startup_cleanup(profiles)
    assert procs.killed == [100]
    for sid in ("1", "2"):
        assert not any((profiles / sid / n).exists() for n in SINGLETON_FILES)
    assert (profiles / "2" / "Cookies").exists()


async def test_startup_cleanup_without_profiles_dir(reg, tmp_path):
    await reg.startup_cleanup(tmp_path / "missing")  # 不报错


async def test_close_shop_and_close_all(reg, procs, profiles):
    a = launcher(procs, profiles / "1", 100)
    b = launcher(procs, profiles / "2", 200)
    async with reg.open(profiles / "1", Purpose.IM, a), reg.open(profiles / "2", Purpose.IM, b):
        assert await reg.close_shop(1, "preempted") is True
        assert await reg.close_shop(1, "preempted") is False
        assert [i.shop_id for i in reg.list()] == [2]
        await reg.close_all("shutdown")
        assert reg.list() == []


async def test_logs_never_carry_paths_or_args(reg, procs, profiles):
    launch = launcher(procs, profiles / "1", 100, hang=True)
    with capture_logs() as logs:
        async with reg.open(profiles / "1", Purpose.LOGIN, launch):
            pass
    text = repr(logs)
    assert str(profiles) not in text and "--" not in text
