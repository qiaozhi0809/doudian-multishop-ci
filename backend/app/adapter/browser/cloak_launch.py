"""CloakBrowser 启动：扫码登录与同步收款信息共用，保证两处是同一套设备环境。

运行时**不下载**浏览器：库在二进制缺失时会在协程里同步下载约 200MB，
整个事件循环（含其他店铺的定时任务和接口）会卡住几分钟。所以启动前先查
二进制是否已按部署文档预下载，没有就直接报错。
"""

import sys
from pathlib import Path

import structlog
from playwright.async_api import Error as PlaywrightError

from app.shared.cloak import cloak_launch_args, get_or_create_seed

log = structlog.get_logger()

BINARY_MISSING = "浏览器未预下载，请按部署文档执行预下载"
LAUNCH_FAILED = "浏览器启动失败，请查看日志"
PROFILE_UNWRITABLE = "该店浏览器资料目录无法读写，请检查资料目录的权限与磁盘空间"
PROFILE_IN_USE = "该店浏览器资料目录正被占用，请先关闭这家店已打开的浏览器窗口再试"
BINARY_NOT_EXECUTABLE = "浏览器程序无法运行，请按部署文档重新预下载"
NOT_INSTALLED = "未安装 cloakbrowser，请先执行：pip install cloakbrowser==0.3.30"


class CloakUnavailable(RuntimeError):
    """CloakBrowser 不可用（未安装、未预下载或启动失败）；消息面向用户，可直接展示。"""


def binary_ready() -> bool:
    """二进制是否已在本地（不触发下载）。与库的 ensure_binary 查找顺序一致。"""
    from cloakbrowser.config import (
        get_binary_path,
        get_effective_version,
        get_local_binary_override,
    )

    override = get_local_binary_override()
    if override:
        return Path(override).is_file()
    return get_binary_path(get_effective_version()).is_file()


def build_cloak_kwargs(profile_dir: Path, proxy: dict | None, *, offscreen: bool = False) -> dict:
    """CloakBrowser 启动参数。proxy 已由 playwright_proxy() 转成 dict。

    有头模式下**必须**显式传 ``viewport=None``：cloakbrowser 在拿不到 viewport
    时会套用写死的 ``DEFAULT_VIEWPORT``（1920x947），与真实窗口尺寸不一致，
    页面会被渲染成错误的缩放比例。传 None 让它设置 ``no_viewport``，
    直接用真实窗口尺寸，屏幕/窗口比例由种子派生的指纹保持一致。
    """
    seed = get_or_create_seed(profile_dir)
    return {
        "user_data_dir": str(profile_dir),
        "headless": False,
        "proxy": proxy,
        "viewport": None,
        "args": cloak_launch_args(seed, proxied=proxy is not None, offscreen=offscreen),
    }


async def launch_cloak(profile_dir: Path, proxy: dict | None, *, offscreen: bool = False):
    """启动该店的 CloakBrowser 持久化上下文；任何启动问题都抛 CloakUnavailable。

    异常消息与日志都不带命令行参数——里面有代理地址和账号密码。
    """
    try:
        from cloakbrowser import launch_persistent_context_async
    except ImportError as exc:
        raise CloakUnavailable(NOT_INSTALLED) from exc
    if not binary_ready():
        raise CloakUnavailable(BINARY_MISSING)
    try:
        kwargs = build_cloak_kwargs(profile_dir, proxy, offscreen=offscreen)
    except OSError as exc:  # 写种子文件失败：目录不可写、磁盘满
        log.warning("cloak.profile_unwritable", error=type(exc).__name__)
        raise CloakUnavailable(PROFILE_UNWRITABLE) from None
    try:
        context = await launch_persistent_context_async(**kwargs)
    except (OSError, PlaywrightError) as exc:
        reason = _launch_reason(exc)
        log.warning("cloak.launch_failed", error=type(exc).__name__, reason=reason)
        raise CloakUnavailable(reason) from None
    if offscreen and _platform() in _MINIMIZE_PLATFORMS:
        await _minimize(context)
    return context


# macOS 会把 --window-position 的屏幕外坐标挪回屏幕内，后台窗口一直露在桌面上，
# 只能启动后最小化（渲染不降速靠 OFFSCREEN_RENDER）
_MINIMIZE_PLATFORMS = frozenset({"darwin"})


def _platform() -> str:
    return sys.platform


async def _minimize(context) -> None:
    """经同一浏览器连接把窗口最小化；失败只记日志，不影响使用。"""
    try:
        page = context.pages[0] if context.pages else await context.new_page()
        cdp = await context.new_cdp_session(page)
        window = await cdp.send("Browser.getWindowForTarget")
        await cdp.send(
            "Browser.setWindowBounds",
            {"windowId": window["windowId"], "bounds": {"windowState": "minimized"}},
        )
        await cdp.detach()
    except Exception as e:  # noqa: BLE001 - 只影响窗口是否露出
        log.warning("cloak.minimize_failed", error=type(e).__name__)


def _launch_reason(exc: Exception) -> str:
    """启动失败的用户提示。只看异常类型和关键词，不回显原消息（里面有代理地址和参数）。"""
    if isinstance(exc, PermissionError):
        return BINARY_NOT_EXECUTABLE
    if isinstance(exc, FileNotFoundError):
        return BINARY_MISSING
    if isinstance(exc, OSError):
        return PROFILE_UNWRITABLE
    text = str(exc)
    if "ProcessSingleton" in text or "SingletonLock" in text or "profile is already in use" in text:
        return PROFILE_IN_USE
    if "EACCES" in text or "Permission denied" in text:
        return PROFILE_UNWRITABLE
    return LAUNCH_FAILED
