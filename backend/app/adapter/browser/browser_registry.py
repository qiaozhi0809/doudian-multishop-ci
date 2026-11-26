"""浏览器登记：本后端启动的每个浏览器（扫码、读页面、飞鸽常驻）都在这里登记与回收。

- 登记：经 ``open()`` / ``open_cloak()`` 启动，按店铺目录登记用途、主进程 pid、启动时间、
  最长存活时间；退出时关闭并注销。关闭有超时，超时或关完进程仍在就强杀整棵进程树。
- 巡检 ``sweep()``：关闭超过最长存活时间的；注销进程已不在的；结束未登记但
  ``--user-data-dir`` 位于 profiles 目录下的孤儿浏览器并清理其锁文件。
- 启动清理 ``startup_cleanup()``：巡检一次，再清掉所有未登记店铺目录里残留的锁文件。

只动 profiles 目录下的进程，绝不碰用户自己的 Chrome。日志只记店铺、用途、原因，
不记路径、命令行（里面有代理账号密码）。
"""

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

import structlog

from app.adapter.browser import cloak_launch
from app.adapter.browser.browser_process import (
    BrowserProc,
    PsutilProcesses,
    owned_profile,
    remove_singleton_files,
    same_dir,
)

log = structlog.get_logger()

CLOSE_TIMEOUT_S = 15
SWEEP_INTERVAL_S = 300


class Purpose(StrEnum):
    LOGIN = "login"
    SCRAPE = "scrape"
    IM = "im"  # 飞鸽只读消息：常驻，到期由巡检关闭，持有方重新 open（即每天重启一次）


MAX_AGE_S: dict[Purpose, float] = {
    Purpose.LOGIN: 10 * 60,
    Purpose.SCRAPE: 2 * 60,
    Purpose.IM: 24 * 3600,
}


class ProcessOps(Protocol):
    def list_browsers(self) -> list[BrowserProc]: ...
    def alive(self, pid: int) -> bool: ...
    def kill_tree(self, pid: int) -> None: ...


@dataclass(frozen=True)
class BrowserInfo:
    """对外只读的登记信息。"""

    shop_id: int | None
    purpose: Purpose
    pid: int | None
    started_at: datetime
    max_age_s: float


@dataclass(eq=False)
class _Entry:
    profile_dir: Path
    purpose: Purpose
    max_age_s: float
    started_at: datetime
    t0: float
    pid: int | None = None
    ctx: Any = None
    closing: asyncio.Task | None = field(default=None, repr=False)

    @property
    def shop_id(self) -> int | None:
        name = self.profile_dir.name
        return int(name) if name.isdigit() else None

    def info(self) -> BrowserInfo:
        return BrowserInfo(self.shop_id, self.purpose, self.pid, self.started_at, self.max_age_s)


class BrowserRegistry:
    def __init__(
        self, procs: ProcessOps | None = None, *, clock: Callable[[], float] = time.monotonic,
        close_timeout_s: float = CLOSE_TIMEOUT_S,
    ) -> None:
        self._procs = procs or PsutilProcesses()
        self._clock = clock
        self._close_timeout_s = close_timeout_s
        self._entries: list[_Entry] = []

    def list(self) -> list[BrowserInfo]:
        return [e.info() for e in self._entries]

    @asynccontextmanager
    async def open(
        self, profile_dir: Path, purpose: Purpose, launch: Callable[[], Awaitable[Any]],
        *, max_age_s: float | None = None,
    ) -> AsyncIterator[Any]:
        """登记并启动；``launch()`` 返回 Playwright 上下文。同一目录已登记时直接拒绝。

        先登记后启动：启动途中的浏览器不会被巡检当成孤儿。
        """
        if any(same_dir(e.profile_dir, profile_dir) for e in self._entries):
            raise cloak_launch.CloakUnavailable(cloak_launch.PROFILE_IN_USE)
        entry = _Entry(
            profile_dir, purpose, MAX_AGE_S[purpose] if max_age_s is None else max_age_s,
            datetime.now(UTC), self._clock(),
        )
        self._entries.append(entry)
        try:
            entry.ctx = await launch()
        except BaseException:
            self._entries.remove(entry)
            raise
        entry.pid = await self._find_pid(profile_dir)
        log.info("browser.opened", shop_id=entry.shop_id, purpose=purpose.value,
                 found_pid=entry.pid is not None)
        try:
            yield entry.ctx
        finally:
            await self._close(entry, "done")

    def open_cloak(
        self, profile_dir: Path, purpose: Purpose, proxy: dict | None, *,
        offscreen: bool = False, max_age_s: float | None = None,
    ):
        """用 CloakBrowser 打开该店浏览器（proxy 为 playwright_proxy() 的结果）。"""
        return self.open(
            profile_dir, purpose,
            lambda: cloak_launch.launch_cloak(profile_dir, proxy, offscreen=offscreen),
            max_age_s=max_age_s,
        )

    async def close_shop(self, shop_id: int, reason: str) -> bool:
        """关闭该店已登记的浏览器（如扫码前让出常驻的飞鸽浏览器）；没有则返回 False。"""
        hits = [e for e in self._entries if e.shop_id == shop_id and e.ctx is not None]
        for e in hits:
            await self._close(e, reason)
        return bool(hits)

    async def close_all(self, reason: str) -> None:
        for e in [e for e in self._entries if e.ctx is not None]:
            await self._close(e, reason)

    async def sweep(self, profiles_dir: Path) -> None:
        now = self._clock()
        for e in list(self._entries):
            if e.ctx is None or e.closing is not None:
                continue  # 还在启动 / 已在关闭
            if now - e.t0 > e.max_age_s:
                await self._close(e, "expired")
            elif e.pid is not None and not await asyncio.to_thread(self._procs.alive, e.pid):
                await self._close(e, "process_gone")
        await self._kill_orphans(profiles_dir)

    async def startup_cleanup(self, profiles_dir: Path) -> None:
        await self._kill_orphans(profiles_dir)
        if not profiles_dir.is_dir():
            return
        for child in profiles_dir.iterdir():
            if child.is_dir() and not self._registered(child):
                self._remove_locks(child, "startup")

    # ---- 内部 ----

    def _registered(self, profile_dir: Path) -> bool:
        return any(same_dir(e.profile_dir, profile_dir) for e in self._entries)

    async def _find_pid(self, profile_dir: Path) -> int | None:
        try:
            procs = await asyncio.to_thread(self._procs.list_browsers)
        except Exception:  # noqa: BLE001 - 取不到 pid 只是少一个强杀依据，仍按目录登记
            return None
        return next((p.pid for p in procs if same_dir(p.user_data_dir, profile_dir)), None)

    async def _kill_orphans(self, profiles_dir: Path) -> None:
        procs = await asyncio.to_thread(self._procs.list_browsers)
        pids = {e.pid for e in self._entries if e.pid is not None}
        for p in procs:
            profile = owned_profile(p.user_data_dir, profiles_dir)
            if profile is None or p.pid in pids or self._registered(profile):
                continue
            await asyncio.to_thread(self._procs.kill_tree, p.pid)
            shop_id = int(profile.name) if profile.name.isdigit() else None
            log.warning("browser.orphan_killed", shop_id=shop_id, reason="orphan")
            self._remove_locks(profile, "orphan")

    def _remove_locks(self, profile_dir: Path, reason: str) -> None:
        removed = remove_singleton_files(profile_dir)
        if removed:
            name = profile_dir.name
            log.info("browser.locks_removed", shop_id=int(name) if name.isdigit() else None,
                     reason=reason, count=len(removed))

    async def _close(self, entry: _Entry, reason: str) -> None:
        """关闭只做一次：巡检与持有方同时关时，后到的等同一个结果。"""
        if entry.closing is None:
            entry.closing = asyncio.ensure_future(self._do_close(entry, reason))
        await asyncio.shield(entry.closing)

    async def _do_close(self, entry: _Entry, reason: str) -> None:
        timed_out = False
        try:
            await asyncio.wait_for(entry.ctx.close(), self._close_timeout_s)
        except TimeoutError:
            timed_out = True
        except Exception:  # noqa: BLE001 - 用户已关窗或浏览器已崩溃时 close 会报错
            pass
        killed = False
        pid = entry.pid if entry.pid is not None else await self._find_pid(entry.profile_dir)
        if pid is not None and await asyncio.to_thread(self._procs.alive, pid):
            await asyncio.to_thread(self._procs.kill_tree, pid)
            killed = True
        if timed_out:  # 浏览器已结束，再关一次让 Playwright 驱动进程退出
            with suppress(Exception):
                await asyncio.wait_for(entry.ctx.close(), self._close_timeout_s)
        if entry in self._entries:
            self._entries.remove(entry)
        log.info("browser.closed", shop_id=entry.shop_id, purpose=entry.purpose.value,
                 reason=reason, killed=killed)


REGISTRY = BrowserRegistry()
"""本后端进程唯一的登记表：扫码、读页面、巡检与飞鸽常驻都用它。"""
