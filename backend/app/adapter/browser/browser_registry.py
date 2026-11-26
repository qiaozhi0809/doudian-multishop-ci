"""浏览器登记：本后端启动的每个浏览器（扫码、读页面、飞鸽常驻）都在这里登记与回收。

- 登记：经 ``open()`` / ``open_cloak()`` 启动，按店铺目录登记用途、主进程 pid、启动时间、
  最长存活时间；退出时关闭并注销。关闭有超时，超时或关完进程仍在就强杀整棵进程树。
- 巡检 ``sweep()``：关闭超过最长存活时间的；注销进程已不在的；结束未登记但
  ``--user-data-dir`` 位于 profiles 目录下的孤儿浏览器并清理其锁文件（browser_sweep）。
- 启动清理 ``startup_cleanup()``：清孤儿，再清掉所有未登记店铺目录里残留的锁文件。
- 进程身份按 (pid, 创建时间, 目录) 核对，pid 被复用时按「已不在」处理，绝不误杀。

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
from typing import Any

import structlog

from app.adapter.browser import browser_sweep, browser_timing, cloak_launch
from app.adapter.browser.browser_process import (
    BrowserProc,
    ProcessOps,
    PsutilProcesses,
    same_dir,
)
from app.adapter.browser.browser_sweep import shop_id_of

log = structlog.get_logger()

CLOSE_TIMEOUT_S = 15
SWEEP_INTERVAL_S = 300


class Purpose(StrEnum):
    LOGIN = "login"
    SCRAPE = "scrape"
    IM = "im"  # 飞鸽只读消息：常驻，到期由巡检关闭，持有方重新 open（即每天重启一次）


class CloseReason(StrEnum):
    """关闭原因（on_close 收到的值）。close_shop / close_all 可传其他原因，原样转交。"""

    DONE = "done"  # 持有方退出 async with
    EXPIRED = "expired"  # 巡检：超过最长存活时间（im 即每日重启）
    PROCESS_GONE = "process_gone"  # 巡检：进程已不在（用户关窗、浏览器崩溃）
    PREEMPTED = "preempted"  # close_shop 让出该店目录（如扫码前关闭常驻 im）
    SHUTDOWN = "shutdown"  # 后端退出


MAX_AGE_S: dict[Purpose, float] = {
    Purpose.LOGIN: browser_timing.login_max_age(),
    Purpose.SCRAPE: browser_timing.SCRAPE_MAX_S,
    Purpose.IM: browser_timing.IM_MAX_S,
}


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
    proc: BrowserProc | None = None
    ctx: Any = None
    on_close: Callable[[str], None] | None = None
    closing: asyncio.Task | None = field(default=None, repr=False)

    @property
    def shop_id(self) -> int | None:
        return shop_id_of(self.profile_dir)

    def info(self) -> BrowserInfo:
        pid = self.proc.pid if self.proc else None
        return BrowserInfo(self.shop_id, self.purpose, pid, self.started_at, self.max_age_s)


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
        *, max_age_s: float | None = None, on_close: Callable[[str], None] | None = None,
    ) -> AsyncIterator[Any]:
        """登记并启动；``launch()`` 返回 Playwright 上下文。同一目录已登记时直接拒绝。

        先登记后启动：启动途中的浏览器不会被巡检当成孤儿。
        ``on_close(reason)`` 在浏览器关闭并注销后调用一次，reason 见 ``CloseReason``
        （``close_shop`` / ``close_all`` 传入的原因原样给出）；启动失败不调用。
        """
        if any(same_dir(e.profile_dir, profile_dir) for e in self._entries):
            raise cloak_launch.CloakUnavailable(cloak_launch.PROFILE_IN_USE)
        entry = _Entry(
            profile_dir, purpose, MAX_AGE_S[purpose] if max_age_s is None else max_age_s,
            datetime.now(UTC), self._clock(), on_close=on_close,
        )
        self._entries.append(entry)
        try:
            entry.ctx = await launch()
        except BaseException:
            self._entries.remove(entry)
            raise
        try:  # 从这里起任何取消或异常都要关浏览器、注销
            entry.proc = await self._find_proc(profile_dir)
            log.info("browser.opened", shop_id=entry.shop_id, purpose=purpose.value,
                     found_pid=entry.proc is not None)
            yield entry.ctx
        finally:
            await self._close(entry, CloseReason.DONE)

    def open_cloak(
        self, profile_dir: Path, purpose: Purpose, proxy: dict | None, *,
        offscreen: bool = False, max_age_s: float | None = None,
        on_close: Callable[[str], None] | None = None,
    ):
        """用 CloakBrowser 打开该店浏览器（proxy 为 playwright_proxy() 的结果）。"""
        return self.open(
            profile_dir, purpose,
            lambda: cloak_launch.launch_cloak(profile_dir, proxy, offscreen=offscreen),
            max_age_s=max_age_s, on_close=on_close,
        )

    async def close_shop(self, shop_id: int, reason: str = CloseReason.PREEMPTED) -> bool:
        """关闭该店已登记的浏览器（如扫码前让出常驻的飞鸽浏览器）；没有则返回 False。

        正在启动（launch 还没返回）的不关、也不算：此时返回 False，调用方随后 open
        会收到「资料目录正被占用」，需自行稍后重试。
        """
        hits = [e for e in self._entries if e.shop_id == shop_id and e.ctx is not None]
        await asyncio.gather(*(self._close(e, reason) for e in hits))
        return bool(hits)

    async def close_all(self, reason: str = CloseReason.SHUTDOWN) -> None:
        """并行关闭：店铺多时逐个关会拖到被服务管理器强杀。"""
        hits = [e for e in self._entries if e.ctx is not None]
        await asyncio.gather(*(self._close(e, reason) for e in hits))

    async def sweep(self, profiles_dir: Path) -> None:
        now = self._clock()
        for e in list(self._entries):
            if e.ctx is None or e.closing is not None:
                continue  # 还在启动 / 已在关闭
            if now - e.t0 > e.max_age_s:
                await self._close(e, CloseReason.EXPIRED)
            elif e.proc is not None and not await asyncio.to_thread(self._procs.alive, e.proc):
                await self._close(e, CloseReason.PROCESS_GONE)
        await self._kill_orphans(profiles_dir)

    async def startup_cleanup(self, profiles_dir: Path) -> None:
        await self._kill_orphans(profiles_dir)
        dirs = [e.profile_dir for e in self._entries]
        await asyncio.to_thread(browser_sweep.clear_stale_locks, profiles_dir, dirs)

    # ---- 内部 ----

    async def _find_proc(self, profile_dir: Path) -> BrowserProc | None:
        try:
            procs = await asyncio.to_thread(self._procs.list_browsers)
        except Exception:  # noqa: BLE001 - 取不到进程只是少一个强杀依据，仍按目录登记
            return None
        return next((p for p in procs if same_dir(p.user_data_dir, profile_dir)), None)

    async def _kill_orphans(self, profiles_dir: Path) -> None:
        dirs = [e.profile_dir for e in self._entries]
        procs = {e.proc for e in self._entries if e.proc is not None}
        await asyncio.to_thread(browser_sweep.kill_orphans, self._procs, profiles_dir, dirs, procs)

    async def _close(self, entry: _Entry, reason: str) -> None:
        """关闭只做一次：巡检与持有方同时关时，后到的等同一个结果。"""
        if entry.closing is None:
            entry.closing = asyncio.ensure_future(self._do_close(entry, reason))
        await asyncio.shield(entry.closing)

    async def _do_close(self, entry: _Entry, reason: str) -> None:
        killed = False
        try:
            timed_out = False
            try:
                await asyncio.wait_for(entry.ctx.close(), self._close_timeout_s)
            except TimeoutError:
                timed_out = True
            except Exception:  # noqa: BLE001 - 用户已关窗或浏览器已崩溃时 close 会报错
                pass
            proc = entry.proc or await self._find_proc(entry.profile_dir)
            if proc is not None:
                killed = await asyncio.to_thread(self._procs.kill_tree, proc)
            if timed_out:  # 浏览器已结束，再关一次让 Playwright 驱动进程退出
                with suppress(Exception):
                    await asyncio.wait_for(entry.ctx.close(), self._close_timeout_s)
        except Exception:  # noqa: BLE001 - 强杀失败也要注销并通知持有方
            log.exception("browser.close_failed", shop_id=entry.shop_id,
                          purpose=entry.purpose.value)
        finally:
            if entry in self._entries:
                self._entries.remove(entry)
            log.info("browser.closed", shop_id=entry.shop_id, purpose=entry.purpose.value,
                     reason=str(reason), killed=killed)
            if entry.on_close is not None:
                try:
                    entry.on_close(str(reason))
                except Exception:  # noqa: BLE001 - 持有方回调出错不影响注销
                    log.exception("browser.on_close_failed", shop_id=entry.shop_id,
                                  purpose=entry.purpose.value)


REGISTRY = BrowserRegistry()
"""本后端进程唯一的登记表：扫码、读页面、巡检与飞鸽常驻都用它。"""
