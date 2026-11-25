import asyncio

import pytest

from app.service.periodic import run_every
from app.service.scheduler import ShopScheduler


class Probe:
    """记录并发度。"""

    def __init__(self) -> None:
        self.active = 0
        self.peak = 0

    async def job(self) -> str:
        self.active += 1
        self.peak = max(self.peak, self.active)
        await asyncio.sleep(0.02)
        self.active -= 1
        return "done"


async def test_same_shop_serial():
    sched, probe = ShopScheduler(3), Probe()
    results = await asyncio.gather(*[sched.run(1, probe.job) for _ in range(4)])
    assert results == ["done"] * 4 and probe.peak == 1


async def test_different_shops_run_concurrently():
    sched, probe = ShopScheduler(3), Probe()
    await asyncio.gather(*[sched.run(i, probe.job) for i in range(3)])
    assert probe.peak == 3


async def test_global_limit():
    sched, probe = ShopScheduler(3), Probe()
    await asyncio.gather(*[sched.run(i, probe.job) for i in range(5)])
    assert probe.peak == 3


async def test_waiting_same_shop_jobs_do_not_hog_global_slots():
    sched, probe = ShopScheduler(2), Probe()
    jobs = [sched.run(1, probe.job) for _ in range(3)] + [sched.run(2, probe.job)]
    await asyncio.gather(*jobs)
    assert probe.peak == 2  # 店 1 排队的任务不占全局名额，店 2 能与店 1 同时跑


async def test_failure_releases_lock_and_slot():
    sched = ShopScheduler(1)

    async def boom():
        raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        await sched.run(1, boom)
    assert await asyncio.wait_for(sched.run(1, Probe().job), 1) == "done"


async def test_run_every_survives_exception():
    calls = 0
    stop = asyncio.Event()

    async def flaky():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("first run fails")
        if calls >= 3:
            stop.set()

    await asyncio.wait_for(run_every(0.01, flaky, stop), 2)
    assert calls == 3


async def test_run_every_stops_promptly():
    stop = asyncio.Event()

    async def noop():
        pass

    task = asyncio.ensure_future(run_every(3600, noop, stop))
    await asyncio.sleep(0.02)
    stop.set()
    await asyncio.wait_for(task, 1)
