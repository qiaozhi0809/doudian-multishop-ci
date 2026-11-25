"""CloakBrowser 指纹种子：每店一个固定值，首次生成后永久复用。

种子决定 CloakBrowser 生成的整套指纹（硬件并发、内存、屏幕、窗口、GPU 等）。
固定种子 = 该店铺永远呈现同一台设备，与「每店固定出口 IP」是同一个思路。
"""

import random
from pathlib import Path

SEED_FILE = ".cloak-seed"
SEED_MIN = 10_000
SEED_MAX = 99_999


def _sibling_seeds(profile_dir: Path) -> set[int]:
    """同级 profile 目录里已被占用的种子。"""
    parent = profile_dir.parent
    if not parent.is_dir():
        return set()
    seeds: set[int] = set()
    for child in parent.iterdir():
        if child == profile_dir or not child.is_dir():
            continue
        marker = child / SEED_FILE
        if not marker.is_file():
            continue
        text = marker.read_text(encoding="ascii", errors="ignore").strip()
        if text.isdigit() and SEED_MIN <= int(text) <= SEED_MAX:
            seeds.add(int(text))
    return seeds


def get_or_create_seed(profile_dir: Path) -> int:
    """读取该 profile 的固定指纹种子；缺失或非法时生成并落盘。

    新种子会避开同级 profile 目录已用的种子，防止复制 profile 目录后
    两家店变成同一台设备。profile 目录不可写时抛 OSError——调用方应据此
    报错，而不是静默换随机值，否则同一店铺的身份会在每次启动时变化。
    """
    profile_dir.mkdir(parents=True, exist_ok=True)
    path = profile_dir / SEED_FILE
    if path.is_file():
        text = path.read_text(encoding="ascii", errors="ignore").strip()
        if text.isdigit() and SEED_MIN <= int(text) <= SEED_MAX:
            return int(text)

    used = _sibling_seeds(profile_dir)
    for _ in range(100):
        seed = random.randint(SEED_MIN, SEED_MAX)
        if seed not in used:
            break
    else:
        # 100 次随机全部撞上（仅当同级种子近乎占满 90_000 个可用值时才会发生）：
        # 线性兜底，保证不同店铺的种子仍然唯一。
        for seed in range(SEED_MIN, SEED_MAX + 1):
            if seed not in used:
                break
        else:
            raise RuntimeError("指纹种子空间已耗尽：同级 profile 数超过可用种子数")

    path.write_text(str(seed), encoding="ascii")
    return seed


def cloak_launch_args(seed: int) -> list[str]:
    """CloakBrowser 启动参数：固定指纹 + 声称 Windows 平台。"""
    return [f"--fingerprint={seed}", "--fingerprint-platform=windows"]
