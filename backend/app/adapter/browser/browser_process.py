"""浏览器进程的操作系统层：枚举带 ``--user-data-dir`` 的浏览器进程、结束整棵进程树、
清理残留的单例锁文件。只翻译操作系统，不决定该结束谁（由 browser_registry / browser_sweep 决定）。

进程身份是 (pid, 创建时间, --user-data-dir) 三元组：每次查活或强杀前都重新核对，
pid 被系统复用给别的进程时按「已不在」处理，绝不去杀。
"""

import os
import socket
import subprocess
import sys
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Protocol

import psutil

USER_DATA_FLAG = "--user-data-dir"
SINGLETON_FILES = ("SingletonLock", "SingletonSocket", "SingletonCookie")
KILL_WAIT_S = 5
CREATE_TIME_TOLERANCE_S = 0.01


@dataclass(frozen=True)
class BrowserProc:
    pid: int
    user_data_dir: str
    create_time: float


class ProcessOps(Protocol):
    def list_browsers(self) -> list[BrowserProc]: ...
    def alive(self, proc: BrowserProc) -> bool: ...
    def kill_tree(self, proc: BrowserProc) -> bool: ...


def user_data_dir_of(cmdline: list[str]) -> str | None:
    """命令行里的 --user-data-dir；支持 ``=值`` 与分开两项两种写法。"""
    for i, arg in enumerate(cmdline):
        if arg.startswith(USER_DATA_FLAG + "="):
            return arg[len(USER_DATA_FLAG) + 1:].strip('"')
        if arg == USER_DATA_FLAG and i + 1 < len(cmdline):
            return cmdline[i + 1].strip('"')
    return None


def top_level(rows: list[tuple[int, int, str, float]]) -> list[BrowserProc]:
    """(pid, ppid, user_data_dir, 创建时间) → 浏览器主进程：父进程不是另一个浏览器进程的那些。"""
    pids = {row[0] for row in rows}
    return [BrowserProc(pid, d, ct) for pid, ppid, d, ct in rows if ppid not in pids]


def _norm(path: str | Path) -> PurePath:
    return PurePath(os.path.normcase(os.path.realpath(path)))


def owned_profile(user_data_dir: str, profiles_dir: Path) -> Path | None:
    """user_data_dir 位于 profiles_dir 之下时，返回它所属的店铺目录 profiles/<名>；否则 None。

    相对路径一律不认（会按本后端的工作目录解析，可能误判）；我们启动的浏览器都传绝对路径。
    macOS 大小写不同、Windows 不存在路径的 8.3 短名都只会导致「不认」，属于安全的失败方向。
    """
    if not os.path.isabs(user_data_dir):
        return None
    root = _norm(profiles_dir)
    target = _norm(user_data_dir)
    if target == root or not target.is_relative_to(root):
        return None
    return profiles_dir / target.relative_to(root).parts[0]


def same_dir(a: str | Path, b: str | Path) -> bool:
    return _norm(a) == _norm(b)


def lock_held_by_live_process(profile_dir: Path, pid_exists=psutil.pid_exists) -> bool:
    """macOS/Linux 的 SingletonLock 是指向 ``主机名-pid`` 的符号链接：本机该 pid 仍在就算占用。

    进程表里看不到（cmdline 无权读取）的浏览器，靠这一步避免删掉它正在用的锁。
    Windows 上锁文件被占用时本来就删不掉，这里返回 False。
    """
    try:
        target = os.readlink(profile_dir / "SingletonLock")
    except OSError:
        return False
    host, _, pid = target.rpartition("-")
    return host == socket.gethostname() and pid.isdigit() and pid_exists(int(pid))


def remove_singleton_files(profile_dir: Path, pid_exists=psutil.pid_exists) -> list[str]:
    """删除残留的 Singleton* 锁文件；锁的持有进程仍在时一个都不删。"""
    if lock_held_by_live_process(profile_dir, pid_exists):
        return []
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
    """真实进程表。方法都是阻塞调用，调用方应放进线程执行。ps / run / platform 供测试替换。"""

    def __init__(self, ps: Any = psutil, run: Any = subprocess.run,
                 platform: str = sys.platform) -> None:
        self._ps, self._run, self._platform = ps, run, platform

    def list_browsers(self) -> list[BrowserProc]:
        rows: list[tuple[int, int, str, float]] = []
        for p in self._ps.process_iter(["pid", "ppid", "cmdline", "create_time"]):
            found = user_data_dir_of(p.info.get("cmdline") or [])  # 无权限读取时为 None
            if found and p.info.get("create_time") is not None:
                rows.append((p.info["pid"], p.info.get("ppid") or 0, found,
                             p.info["create_time"]))
        return top_level(rows)

    def _verified(self, proc: BrowserProc) -> Any:
        """pid 仍是登记时那个浏览器才返回 psutil.Process；被复用、已退出、目录不符都返回 None。"""
        try:
            p = self._ps.Process(proc.pid)
            if abs(p.create_time() - proc.create_time) > CREATE_TIME_TOLERANCE_S:
                return None
            if p.status() == self._ps.STATUS_ZOMBIE:
                return None
            found = user_data_dir_of(p.cmdline() or [])
            if found is None or not same_dir(found, proc.user_data_dir):
                return None
            return p
        except self._ps.Error:
            return None

    def alive(self, proc: BrowserProc) -> bool:
        return self._verified(proc) is not None

    def kill_tree(self, proc: BrowserProc) -> bool:
        """结束整棵进程树；身份核对不过时什么都不做并返回 False。

        先挂起主进程（防止它在杀子进程期间重新拉起 GPU / 网络子进程），按快照逐个结束；
        psutil 的 Process 对象自带 pid 复用检查。仍存活的逐个兜底（Windows 用不带 /T 的
        taskkill）；主进程最终没杀掉就恢复运行，不留在挂起状态。最后补杀漏网子进程，
        条件很严（见 ``_late_children``），宁可漏杀不可误杀。
        """
        root = self._verified(proc)
        if root is None:
            return False
        with suppress(self._ps.Error):
            root.suspend()
        try:
            procs = [root, *root.children(recursive=True)]
        except self._ps.Error:
            procs = [root]
        born: dict[int, float] = {}  # 已杀进程 pid → 它自己的创建时间
        for p in procs:
            with suppress(self._ps.Error):
                born[p.pid] = p.create_time()
        self._kill_all(procs)
        with suppress(self._ps.Error):
            if root.is_running():
                root.resume()
        late = self._late_children(born, proc.user_data_dir)
        if late:
            self._kill_all(late)
        return True

    def _late_children(self, born: dict[int, float], user_data_dir: str) -> list[Any]:
        """快照之后才拉起的子进程：父进程是刚杀掉的某个进程、创建时间不早于**那个父进程**、
        命令行带同一个 --user-data-dir。

        Windows 上 ppid 不随父进程退出而更新，pid 也可能已被复用，只凭 ppid 会误杀无关进程。
        """
        late = []
        for q in self._ps.process_iter(["pid", "ppid", "create_time", "cmdline"]):
            info = q.info
            parent_born = born.get(info.get("ppid"))
            if parent_born is None or info["pid"] in born:
                continue
            if (info.get("create_time") or 0) < parent_born:
                continue
            found = user_data_dir_of(info.get("cmdline") or [])
            if found is not None and same_dir(found, user_data_dir):
                late.append(q)
        return late

    def _kill_all(self, procs: list[Any]) -> None:
        for p in procs:
            with suppress(self._ps.Error):
                p.kill()
        _, alive = self._ps.wait_procs(procs, timeout=KILL_WAIT_S)
        for p in alive:
            try:
                if not p.is_running():  # 带 pid 复用检查：已不是原来那个进程就跳过
                    continue
            except self._ps.Error:
                continue
            with suppress(self._ps.Error):
                p.kill()
            if self._platform == "win32":  # kill 抛 AccessDenied 时也要兜底
                with suppress(subprocess.TimeoutExpired, OSError):
                    self._run(  # noqa: S603 - 固定参数，pid 为整数，已核对身份
                        ["taskkill", "/PID", str(p.pid), "/F"],
                        capture_output=True, timeout=KILL_WAIT_S * 2, check=False,
                    )
