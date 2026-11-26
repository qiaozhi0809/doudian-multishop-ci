"""浏览器进程的操作系统层：命令行解析、顶层进程筛选、profiles 归属判定、残留锁清理。"""

import os
import sys

import pytest

from app.adapter.browser.browser_process import (
    SINGLETON_FILES,
    BrowserProc,
    owned_profile,
    remove_singleton_files,
    top_level,
    user_data_dir_of,
)


def test_user_data_dir_from_equals_form():
    cmd = ["/x/chrome", "--fingerprint=12345", "--user-data-dir=/data/profiles/7", "about:blank"]
    assert user_data_dir_of(cmd) == "/data/profiles/7"


def test_user_data_dir_from_split_form_and_quotes():
    assert user_data_dir_of(["chrome.exe", "--user-data-dir", r"C:\d\profiles\3"]) == (
        r"C:\d\profiles\3")
    assert user_data_dir_of(['--user-data-dir="C:\\d\\p\\3"']) == "C:\\d\\p\\3"


def test_user_data_dir_absent():
    assert user_data_dir_of(["python", "-m", "app"]) is None
    assert user_data_dir_of([]) is None


def test_top_level_drops_children_of_matched_browsers():
    rows = [
        (100, 1, "/p/1"),   # 浏览器主进程
        (101, 100, "/p/1"),  # 渲染进程：父进程也是浏览器 → 不算顶层
        (200, 50, "/p/2"),  # 另一家店的主进程
        (300, 999, "/p/3"),  # 父进程已死的孤儿子进程 → 视为顶层
    ]
    assert top_level(rows) == [
        BrowserProc(100, "/p/1"), BrowserProc(200, "/p/2"), BrowserProc(300, "/p/3"),
    ]


def test_owned_profile_returns_shop_dir(tmp_path):
    profiles = tmp_path / "profiles"
    (profiles / "7").mkdir(parents=True)
    assert owned_profile(str(profiles / "7"), profiles) == profiles / "7"
    # 子目录也归属该店目录
    assert owned_profile(str(profiles / "7" / "Default"), profiles) == profiles / "7"


def test_owned_profile_rejects_outside_dirs(tmp_path):
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    assert owned_profile(str(tmp_path / "profiles2" / "7"), profiles) is None  # 前缀相同的兄弟目录
    assert owned_profile(str(profiles), profiles) is None  # profiles 目录本身
    assert owned_profile(str(tmp_path / "chrome-user"), profiles) is None  # 用户自己的 Chrome
    assert owned_profile(str(profiles / ".." / "x"), profiles) is None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 路径大小写不敏感")
def test_owned_profile_case_insensitive_on_windows(tmp_path):
    profiles = tmp_path / "profiles"
    (profiles / "7").mkdir(parents=True)
    assert owned_profile(str(profiles / "7").upper(), profiles) is not None


def test_remove_singleton_files_only_removes_lock_names(tmp_path):
    for name in SINGLETON_FILES:
        (tmp_path / name).write_text("x")
    (tmp_path / "Cookies").write_text("keep")
    removed = remove_singleton_files(tmp_path)
    assert sorted(removed) == sorted(SINGLETON_FILES)
    assert [p.name for p in tmp_path.iterdir()] == ["Cookies"]


@pytest.mark.skipif(sys.platform == "win32", reason="SingletonLock 在 macOS/Linux 是悬空符号链接")
def test_remove_singleton_files_handles_dangling_symlink(tmp_path):
    os.symlink("host-12345", tmp_path / "SingletonLock")
    assert remove_singleton_files(tmp_path) == ["SingletonLock"]
    assert not os.path.lexists(tmp_path / "SingletonLock")


def test_remove_singleton_files_missing_dir(tmp_path):
    assert remove_singleton_files(tmp_path / "nope") == []
