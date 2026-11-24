import asyncio

import pytest

from app.service.background import TaskAlreadyRunning, TaskRegistry


async def test_same_name_cannot_run_twice_and_frees_after_finish():
    reg = TaskRegistry()
    gate = asyncio.Event()

    async def work():
        await gate.wait()
        return "done"

    task = reg.spawn("a", work())
    assert reg.is_running("a")
    with pytest.raises(TaskAlreadyRunning):
        reg.spawn("a", work())
    gate.set()
    assert await task == "done"
    await asyncio.sleep(0)
    assert not reg.is_running("a")
    await reg.spawn("a", work())  # 可以再次启动


async def test_failure_is_logged_not_raised_and_registry_cleans_up(capsys):
    from app.shared.logging_setup import configure_logging

    configure_logging(json=True)
    reg = TaskRegistry()

    async def boom():
        raise RuntimeError("secret detail")

    task = reg.spawn("b", boom())
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.sleep(0)
    out = capsys.readouterr().out
    assert "background.failed" in out and "RuntimeError" in out and "secret detail" not in out
    assert not reg.is_running("b")


async def test_shutdown_cancels_running_tasks():
    reg = TaskRegistry()
    task = reg.spawn("c", asyncio.sleep(60))
    await reg.shutdown()
    assert task.cancelled()
