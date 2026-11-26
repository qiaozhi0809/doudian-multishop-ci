"""PsutilProcesses：假 psutil 层覆盖身份核对、进程树结束顺序、Windows 兜底；
再用真实子进程验证枚举与结束整棵树（macOS / Windows CI 都跑）。"""

import subprocess
import sys
import time
from dataclasses import dataclass, field

import psutil
import pytest

from app.adapter.browser.browser_process import BrowserProc, PsutilProcesses, owned_profile

DIR = "/data/profiles/1"


class NoSuchProcess(Exception):
    pass


@dataclass
class Row:
    ppid: int
    cmdline: list[str] | None
    ct: float
    status: str = "running"
    unkillable: bool = False  # psutil kill 不掉，只能靠 taskkill
    children: list[int] = field(default_factory=list)


class FakePs:
    Error = NoSuchProcess
    STATUS_ZOMBIE = "zombie"

    def __init__(self, rows: dict[int, Row]) -> None:
        self.rows = rows
        self.events: list[str] = []

    def Process(self, pid):  # noqa: N802 - 与 psutil 同名
        if pid not in self.rows:
            raise NoSuchProcess(pid)
        return FakeProcess(self, pid, self.rows[pid].ct)

    def process_iter(self, attrs):
        for pid, r in list(self.rows.items()):
            p = FakeProcess(self, pid, r.ct)
            p.info = {"pid": pid, "ppid": r.ppid, "cmdline": r.cmdline, "create_time": r.ct}
            yield p

    def wait_procs(self, procs, timeout):
        alive = [p for p in procs if p.is_running()]
        return [p for p in procs if p not in alive], alive


class FakeProcess:
    def __init__(self, ps: FakePs, pid: int, ct: float) -> None:
        self.ps, self.pid, self._ct = ps, pid, ct

    def _row(self) -> Row:
        r = self.ps.rows.get(self.pid)
        if r is None or r.ct != self._ct:  # 与 psutil 一样：pid 被复用时视为不存在
            raise NoSuchProcess(self.pid)
        return r

    def create_time(self):
        return self._row().ct

    def status(self):
        return self._row().status

    def cmdline(self):
        return self._row().cmdline

    def suspend(self):
        self._row()
        self.ps.events.append(f"suspend {self.pid}")

    def children(self, recursive=False):
        return [FakeProcess(self.ps, c, self.ps.rows[c].ct) for c in self._row().children]

    def kill(self):
        r = self._row()
        self.ps.events.append(f"kill {self.pid}")
        if not r.unkillable:
            del self.ps.rows[self.pid]

    def is_running(self):
        try:
            self._row()
            return True
        except NoSuchProcess:
            return False


def browser_row(ppid=1, ct=100.0, children=None, **kw) -> Row:
    return Row(ppid, ["chrome", f"--user-data-dir={DIR}"], ct, children=children or [], **kw)


def test_list_browsers_returns_main_process_with_create_time():
    ps = FakePs({
        10: browser_row(children=[11]),
        11: Row(10, ["chrome", "--type=renderer", f"--user-data-dir={DIR}"], 101.0),
        20: Row(1, None, 5.0),  # 无权读取 cmdline
        30: Row(1, ["python"], 6.0),
    })
    assert PsutilProcesses(ps).list_browsers() == [BrowserProc(10, DIR, 100.0)]


def test_alive_checks_identity():
    ps = FakePs({10: browser_row()})
    procs = PsutilProcesses(ps)
    assert procs.alive(BrowserProc(10, DIR, 100.0))
    assert not procs.alive(BrowserProc(10, DIR, 99.0))  # pid 被复用
    assert not procs.alive(BrowserProc(10, "/data/profiles/2", 100.0))  # 目录不符
    assert not procs.alive(BrowserProc(99, DIR, 100.0))  # 已退出
    ps.rows[10].status = "zombie"
    assert not procs.alive(BrowserProc(10, DIR, 100.0))


def test_kill_tree_never_touches_reused_pid():
    ps = FakePs({10: Row(1, ["msedge.exe"], 500.0, children=[11]), 11: Row(10, ["x"], 501.0)})
    assert PsutilProcesses(ps).kill_tree(BrowserProc(10, DIR, 100.0)) is False
    assert ps.events == [] and set(ps.rows) == {10, 11}


def test_kill_tree_suspends_then_kills_whole_tree():
    ps = FakePs({
        10: browser_row(children=[11, 12]),
        11: Row(10, ["gpu"], 101.0), 12: Row(10, ["renderer"], 102.0),
        99: Row(1, ["unrelated"], 1.0),
    })
    assert PsutilProcesses(ps).kill_tree(BrowserProc(10, DIR, 100.0)) is True
    assert ps.events[0] == "suspend 10"
    assert set(ps.rows) == {99}


def test_kill_tree_catches_child_spawned_after_snapshot():
    ps = FakePs({10: browser_row(children=[11]), 11: Row(10, ["gpu"], 101.0),
                 12: Row(10, ["network"], 150.0),  # 不在快照里
                 13: Row(10, ["old"], 50.0)})  # 早于主进程：pid 复用前的旧子进程，不碰
    PsutilProcesses(ps).kill_tree(BrowserProc(10, DIR, 100.0))
    assert set(ps.rows) == {13}


def test_windows_fallback_taskkills_each_survivor_without_tree_flag():
    ps = FakePs({10: browser_row(children=[11]), 11: Row(10, ["gpu"], 101.0, unkillable=True)})
    calls = []

    def run(args, **kw):
        calls.append(args)
        if args[2] == "11":
            raise subprocess.TimeoutExpired(args, 10)  # 超时不外抛

    PsutilProcesses(ps, run=run, platform="win32").kill_tree(BrowserProc(10, DIR, 100.0))
    assert calls == [["taskkill", "/PID", "11", "/F"]]


def test_no_taskkill_off_windows():
    ps = FakePs({10: browser_row(unkillable=True)})
    calls = []
    PsutilProcesses(ps, run=lambda a, **k: calls.append(a), platform="darwin").kill_tree(
        BrowserProc(10, DIR, 100.0))
    assert calls == []


def _gone(pid: int) -> bool:
    try:
        return psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    except psutil.Error:
        return True


def test_real_process_tree_is_listed_and_killed(tmp_path):
    profile = tmp_path / "profiles" / "1"
    profile.mkdir(parents=True)
    flag = f"--user-data-dir={profile}"
    child_code = "import time; time.sleep(60)"
    parent_code = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', {child_code!r}, sys.argv[1]]); "
        "time.sleep(60)"
    )
    parent = subprocess.Popen([sys.executable, "-c", parent_code, flag])
    try:
        deadline = time.monotonic() + 10
        while not psutil.Process(parent.pid).children() and time.monotonic() < deadline:
            time.sleep(0.05)
        [child] = psutil.Process(parent.pid).children()
        procs = PsutilProcesses()
        ours = [p for p in procs.list_browsers()
                if owned_profile(p.user_data_dir, tmp_path / "profiles") is not None]
        assert [p.pid for p in ours] == [parent.pid]  # 子进程不算顶层
        assert procs.alive(ours[0])
        assert procs.kill_tree(ours[0]) is True
        parent.wait(timeout=10)
        deadline = time.monotonic() + 10
        while not _gone(child.pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert _gone(child.pid)
        assert not procs.alive(ours[0])
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait()


@pytest.mark.skipif(sys.platform == "win32", reason="只在 POSIX 上能稳定构造 pid 复用的等价情形")
def test_real_reused_identity_is_not_killed():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        fake = BrowserProc(proc.pid, "/nowhere/profiles/1", psutil.Process(proc.pid).create_time())
        assert PsutilProcesses().kill_tree(fake) is False  # cmdline 没有该目录
        assert proc.poll() is None
    finally:
        proc.kill()
        proc.wait()
