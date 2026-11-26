"""浏览器进程的操作系统层：枚举带 ``--user-data-dir`` 的浏览器进程、结束整棵进程树、
清理残留的单例锁文件。只翻译操作系统，不决定该结束谁（由 browser_registry 决定）。

结束进程树用 psutil（Windows / macOS 通用）：先杀全部子进程再杀主进程；
Windows 上如仍有存活，再用 ``taskkill /T /F`` 兜底。
"""

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePath

import psutil

USER_DATA_FLAG = "--user-data-dir"
SINGLETON_FILES = ("SingletonLock", "SingletonSocket", "SingletonCookie")
KILL_WAIT_S = 5


@dataclass(frozen=True)
class BrowserProc:
    pid: int
    user_data_dir: str


def user_data_dir_of(cmdline: list[str]) -> str | None:
    """命令行里的 --user-data-dir；支持 ``=值`` 与分开两项两种写法。"""
    for i, arg in enumerate(cmdline):
        if arg.startswith(USER_DATA_FLAG + "="):
            return arg[len(USER_DATA_FLAG) + 1:].strip('"')
        if arg == USER_DATA_FLAG and i + 1 < len(cmdline):
            return cmdline[i + 1].strip('"')
    return None


def top_level(rows: list[tuple[int, int, str]]) -> list[BrowserProc]:
    """(pid, ppid, user_data_dir) → 浏览器主进程：父进程不是另一个浏览器进程的那些。"""
    pids = {pid for pid, _, _ in rows}
    return [BrowserProc(pid, d) for pid, ppid, d in rows if ppid not in pids]


def _norm(path: str | Path) -> PurePath:
    return PurePath(os.path.normcase(os.path.realpath(path)))


def owned_profile(user_data_dir: str, profiles_dir: Path) -> Path | None:
    """user_data_dir 位于 profiles_dir 之下时，返回它所属的店铺目录 profiles/<名>；否则 None。"""
    root = _norm(profiles_dir)
    target = _norm(user_data_dir)
    if target == root or not target.is_relative_to(root):
        return None
    return profiles_dir / target.relative_to(root).parts[0]


def same_dir(a: str | Path, b: str | Path) -> bool:
    return _norm(a) == _norm(b)


def remove_singleton_files(profile_dir: Path) -> list[str]:
    """删除残留的 Singleton* 锁文件（macOS/Linux 上 SingletonLock 是悬空符号链接）。"""
    removed = []
    for name in SINGLETON_FILES:
        path = profile_dir / name
        if not os.path.lexists(path):
            continue
        try:
            path.unlink()
            removed.append(name)
        except OSError:
            pass
    return removed


class PsutilProcesses:
    """真实进程表。方法都是阻塞调用，调用方应放进线程执行。"""

    def list_browsers(self) -> list[BrowserProc]:
        rows: list[tuple[int, int, str]] = []
        for p in psutil.process_iter(["pid", "ppid", "cmdline"]):
            cmdline = p.info.get("cmdline") or []  # 无权限读取时为 None
            found = user_data_dir_of(cmdline)
            if found:
                rows.append((p.info["pid"], p.info.get("ppid") or 0, found))
        return top_level(rows)

    def alive(self, pid: int) -> bool:
        try:
            return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
        except psutil.Error:
            return False

    def kill_tree(self, pid: int) -> None:
        try:
            root = psutil.Process(pid)
            procs = [*root.children(recursive=True), root]
        except psutil.Error:
            return
        for p in procs:
            try:
                p.kill()
            except psutil.Error:
                pass
        _, alive = psutil.wait_procs(procs, timeout=KILL_WAIT_S)
        if alive and sys.platform == "win32":
            subprocess.run(  # noqa: S603 - 固定参数，pid 为整数
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True, timeout=KILL_WAIT_S * 2, check=False,
            )
