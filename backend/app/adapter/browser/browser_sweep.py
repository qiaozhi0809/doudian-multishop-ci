"""孤儿浏览器与残留锁的清理：整轮「枚举 → 判定归属 → 强杀 → 删锁」在一个线程里同步完成，
事件循环只负责把当前登记的目录与进程交过来。

只动 ``--user-data-dir`` 位于 profiles 目录下、且不在登记表里的进程，绝不碰用户自己的 Chrome。
"""

from pathlib import Path

import structlog

from app.adapter.browser.browser_process import (
    BrowserProc,
    ProcessOps,
    owned_profile,
    remove_singleton_files,
    same_dir,
)

log = structlog.get_logger()


def shop_id_of(profile_dir: Path) -> int | None:
    name = profile_dir.name
    return int(name) if name.isdigit() else None


def _registered(profile_dir: Path, registered_dirs: list[Path]) -> bool:
    return any(same_dir(d, profile_dir) for d in registered_dirs)


def remove_locks(profile_dir: Path, reason: str) -> None:
    removed = remove_singleton_files(profile_dir)
    if removed:
        log.info("browser.locks_removed", shop_id=shop_id_of(profile_dir), reason=reason,
                 count=len(removed))


def kill_orphans(
    procs: ProcessOps, profiles_dir: Path, registered_dirs: list[Path],
    registered_procs: set[BrowserProc],
) -> None:
    for p in procs.list_browsers():
        profile = owned_profile(p.user_data_dir, profiles_dir)
        if profile is None or p in registered_procs or _registered(profile, registered_dirs):
            continue
        if not procs.kill_tree(p):  # 枚举之后已退出或 pid 被复用：不算孤儿
            continue
        log.warning("browser.orphan_killed", shop_id=shop_id_of(profile), reason="orphan")
        remove_locks(profile, "orphan")


def clear_stale_locks(profiles_dir: Path, registered_dirs: list[Path]) -> None:
    if not profiles_dir.is_dir():
        return
    for child in profiles_dir.iterdir():
        if child.is_dir() and not _registered(child, registered_dirs):
            remove_locks(child, "startup")
