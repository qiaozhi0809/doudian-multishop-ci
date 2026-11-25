"""CloakBrowser 指纹种子：每店一个固定值，首次生成后永久复用。

种子决定 CloakBrowser 生成的整套指纹（硬件并发、内存、屏幕、窗口、GPU 等）。
固定种子 = 该店铺永远呈现同一台设备，与「每店固定出口 IP」是同一个思路。
"""

import random
from pathlib import Path

SEED_FILE = ".cloak-seed"
SEED_MIN = 10_000
SEED_MAX = 99_999


def get_or_create_seed(profile_dir: Path) -> int:
    """读取该 profile 的固定指纹种子；缺失或非法时生成并落盘。

    profile 目录不可写时抛 OSError——调用方应据此报错，而不是静默换随机值，
    否则同一店铺的身份会在每次启动时变化。
    """
    profile_dir.mkdir(parents=True, exist_ok=True)
    path = profile_dir / SEED_FILE
    if path.is_file():
        text = path.read_text(encoding="ascii", errors="ignore").strip()
        if text.isdigit() and SEED_MIN <= int(text) <= SEED_MAX:
            return int(text)

    seed = random.randint(SEED_MIN, SEED_MAX)
    path.write_text(str(seed), encoding="ascii")
    return seed


def cloak_launch_args(seed: int) -> list[str]:
    """CloakBrowser 启动参数：固定指纹 + 声称 Windows 平台。"""
    return [f"--fingerprint={seed}", "--fingerprint-platform=windows"]
