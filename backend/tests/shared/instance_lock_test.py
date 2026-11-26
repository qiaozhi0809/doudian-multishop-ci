"""单实例锁：同一数据目录第二次取锁失败，释放后可再取；跨进程同样生效。"""

import subprocess
import sys

from app.shared import instance_lock


def test_second_acquire_fails_until_released(tmp_path):
    first = instance_lock.acquire(tmp_path)
    assert first is not None
    assert instance_lock.acquire(tmp_path) is None
    first.release()
    first.release()  # 重复释放无害
    again = instance_lock.acquire(tmp_path)
    assert again is not None
    again.release()


def test_lock_is_held_against_another_process(tmp_path):
    lock = instance_lock.acquire(tmp_path)
    try:
        code = (
            "import sys; from pathlib import Path; from app.shared import instance_lock; "
            "sys.exit(0 if instance_lock.acquire(Path(sys.argv[1])) is None else 1)"
        )
        assert subprocess.run([sys.executable, "-c", code, str(tmp_path)]).returncode == 0
    finally:
        lock.release()


def test_creates_data_dir(tmp_path):
    lock = instance_lock.acquire(tmp_path / "new" / "data")
    assert lock is not None and (tmp_path / "new" / "data" / instance_lock.LOCK_FILE_NAME).exists()
    lock.release()
