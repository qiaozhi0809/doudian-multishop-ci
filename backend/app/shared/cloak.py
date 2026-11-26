"""CloakBrowser 指纹种子：每店一个固定值，首次生成后永久复用。

种子决定 CloakBrowser 生成的整套指纹（硬件并发、内存、屏幕、窗口、GPU 等）。
固定种子 = 该店铺永远呈现同一台设备，与「每店固定出口 IP」是同一个思路。
同级 profile 目录之间的种子互不重复；复制 profile 目录产生的重复值会被
检测，并且只重建 shop_id 较大（目录名即 shop_id）的那一方：老店保留原种子，
不管谁先启动，结果都一样。
"""

import os
import random
from pathlib import Path

import structlog

log = structlog.get_logger()

SEED_FILE = ".cloak-seed"
SEED_MIN = 10_000
SEED_MAX = 99_999


def _sibling_seeds(profile_dir: Path) -> dict[int, list[str]]:
    """同级 profile 目录里已被占用的种子 → 占用它的目录名。"""
    parent = profile_dir.parent
    if not parent.is_dir():
        return {}
    try:
        own = profile_dir.resolve()
    except (OSError, RuntimeError):
        own = profile_dir
    seeds: dict[int, list[str]] = {}
    for child in parent.iterdir():
        if not child.is_dir():
            continue
        try:
            # 跳过自身及指向自身的别名（pytest 的 <name>current 符号链接等），
            # 否则会把本目录的种子误当成同级已用值而反复重建。
            if child.resolve() == own:
                continue
        except (OSError, RuntimeError):
            continue
        marker = child / SEED_FILE
        if not marker.is_file():
            continue
        try:
            text = marker.read_text(encoding="ascii", errors="ignore").strip()
        except OSError:
            continue
        if text.isdigit() and SEED_MIN <= int(text) <= SEED_MAX:
            seeds.setdefault(int(text), []).append(child.name)
    return seeds


def _order(name: str) -> tuple[int, int, str]:
    """目录名即 shop_id，按数字比较（店 9 先于店 10）；非数字目录排在后面。"""
    return (0, int(name), "") if name.isdigit() else (1, 0, name)


def _shop_id(name: str) -> int | str:
    return int(name) if name.isdigit() else name


def get_or_create_seed(profile_dir: Path) -> int:
    """读取该 profile 的固定指纹种子；缺失或非法时生成并落盘。

    新种子会避开同级 profile 目录已用的种子。已有种子与同级目录冲突
    （例如复制 profile 目录导致）时，只有 shop_id 较大的一方重建，并记
    ``cloak.seed_rebuilt`` 告警；shop_id 较小的老店保留原种子（禁止轮换老店指纹）。
    这样不同店铺不会呈现同一台设备。profile 目录不可写时抛 OSError——调用方应据此
    报错，而不是静默换随机值，否则同一店铺的身份会在每次启动时变化。
    """
    profile_dir.mkdir(parents=True, exist_ok=True)
    path = profile_dir / SEED_FILE
    used = _sibling_seeds(profile_dir)
    if path.is_file():
        text = path.read_text(encoding="ascii", errors="ignore").strip()
        if text.isdigit() and SEED_MIN <= int(text) <= SEED_MAX:
            seed = int(text)
            # 与同级目录冲突（复制 profile 导致）：只有比所有占用者 shop_id 都小才保留
            own = _order(profile_dir.name)
            if all(own < _order(other) for other in used.get(seed, [])):
                return seed
            log.warning("cloak.seed_rebuilt", shop_id=_shop_id(profile_dir.name))

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


WEBRTC_PROXY_ONLY = "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"
OFFSCREEN_WINDOW = "--window-position=-32000,-32000"
# 屏幕外窗口在 Windows 上会被判为「被遮挡」，页面转为 hidden、定时器被节流，
# 懒挂载的微应用读不到。macOS 会把屏幕外坐标挪回屏幕内，改为启动后最小化
# （cloak_launch），后两项保证最小化后渲染与定时器不降速（飞鸽常驻页实测
# 最小化 14 分钟仍可见、心跳与消息照常，2026-11-26）。都是渲染策略参数，不是指纹参数。
OFFSCREEN_RENDER = (
    "--disable-features=CalculateNativeWinOcclusion",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
)


def cloak_launch_args(seed: int, *, proxied: bool = False, offscreen: bool = False) -> list[str]:
    """CloakBrowser 启动参数：固定指纹 + 声称 Windows 平台 + 静音提示条。

    - ``proxied``：经代理时禁止 WebRTC 走非代理的 UDP。HTTP 代理不转发 UDP，
      默认策略会经 STUN 直连拿到本机真实公网 IP，让「每店独立出口」失效。直连店不加。
    - ``offscreen``：有头窗口放到屏幕外，用于不需要人操作的后台读取（同步收款信息）；
      同时关掉遮挡判定，避免页面被当成 hidden 而不挂载。

    后两项是**纯 UI 参数**，不是指纹配置：
    - ``--test-type`` 让 Chromium 认为处在自动化环境，抑制
      「您使用的是不受支持的命令行标记：--no-sandbox」横幅。cloakbrowser 自己
      会加 ``--no-sandbox``，不加这个每个窗口顶部都会挂一条黄条。
      js-reverse-mcp 的 cloak 模式同样传它（见其 browser.js 注释）。
    - ``--hide-crash-restore-bubble`` 隐藏「Chrome 未正常关闭」气泡。
    """
    args = [
        f"--fingerprint={seed}",
        "--fingerprint-platform=windows",
        "--test-type",
        "--hide-crash-restore-bubble",
    ]
    if proxied:
        args.append(WEBRTC_PROXY_ONLY)
    if offscreen:
        args.append(OFFSCREEN_WINDOW)
        args.extend(OFFSCREEN_RENDER)
    return args


def apply_env(cache_dir: Path) -> None:
    """把 CloakBrowser 的缓存目录锁到项目内，并**强制**关闭全部自动更新。

    CLOAKBROWSER_AUTO_UPDATE 无条件写小写字面量 "false"：禁用自动更新是硬约束，
    外部环境变量不得覆盖——库只在值为 false 时才跳过「二进制更新」和「PyPI 包
    更新」两个后台检查。必须在 import cloakbrowser 之前调用。

    缓存目录用 setdefault：那是用户可配置项，显式设置应当被尊重。
    """
    os.environ.setdefault("CLOAKBROWSER_CACHE_DIR", str(cache_dir))
    os.environ["CLOAKBROWSER_AUTO_UPDATE"] = "false"
