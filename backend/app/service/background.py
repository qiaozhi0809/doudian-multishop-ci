"""后台任务登记：持有任务引用、记录异常、关闭时统一取消；同名任务不并发。"""

import asyncio
from collections.abc import Coroutine
from typing import Any

import structlog

log = structlog.get_logger()


class TaskAlreadyRunning(Exception):
    """同名后台任务还在运行。"""


class TaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}

    def is_running(self, name: str) -> bool:
        return name in self._tasks

    def spawn(self, name: str, coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        if name in self._tasks:
            coro.close()
            raise TaskAlreadyRunning(f"任务进行中: {name}")
        task = asyncio.get_running_loop().create_task(coro, name=name)
        self._tasks[name] = task
        task.add_done_callback(lambda t: self._finished(name, t))
        return task

    def _finished(self, name: str, task: asyncio.Task) -> None:
        self._tasks.pop(name, None)
        if not task.cancelled() and task.exception() is not None:
            # 只记异常类型：异常信息可能含敏感内容
            log.warning("background.failed", task=name, error=type(task.exception()).__name__)

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
