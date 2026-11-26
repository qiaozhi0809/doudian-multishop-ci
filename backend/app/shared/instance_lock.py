"""单实例锁：同一个数据目录只允许一个后端在跑。

第二个实例若照常启动，会把第一个实例登记的浏览器当孤儿杀掉、删掉还在用的锁文件，
还会重复做数据库迁移与任务复位。所以 lifespan 第一件事就取这把锁，拿不到立即退出。

锁是操作系统层面的文件锁（POSIX ``fcntl.flock``、Windows ``msvcrt.locking``），
进程退出（含被杀、崩溃）时由系统自动释放，不会留下「假占用」。
"""

import os
import sys
from pathlib import Path

LOCK_FILE_NAME = "app.lock"


class InstanceLock:
    def __init__(self, fd: int) -> None:
        self._fd: int | None = fd

    def release(self) -> None:
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            if sys.platform == "win32":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            os.close(fd)


def acquire(data_dir: Path) -> InstanceLock | None:
    """不阻塞地取得 data_dir 的实例锁；已被别的实例持有时返回 None。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    fd = os.open(data_dir / LOCK_FILE_NAME, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return InstanceLock(fd)
