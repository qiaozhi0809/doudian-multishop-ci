"""Playwright 扫码登录（浏览器通道）。经该店固定出口，用该店独立 profile。

登录成功的判据：首个带 `__token=` 的 fxg.jinritemai.com 请求。cookie 取
`context.cookies()` 的完整列表（含 HttpOnly 与 domain / path）。
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from playwright.async_api import async_playwright

from app.adapter.doudian.endpoints import BASE_URL
from app.shared.cloak import cloak_launch_args, get_or_create_seed

ORDER_PAGE_URL = BASE_URL + "/ffa/morder/order/list"
SESSION_LIFETIME = timedelta(days=60)
LOAD_WAIT_MS = 10_000
_HOST = urlparse(BASE_URL).hostname
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
# 协议通道要复用的设备请求头（规范名）
_DEVICE_HEADERS = ("User-Agent", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform")


@dataclass(frozen=True)
class LoginResult:
    cookies: list[dict]
    token: str
    expires_at: str
    device_headers: dict[str, str]


class CloakUnavailable(RuntimeError):
    """CloakBrowser 不可用（未安装或启动失败）；消息面向用户，可直接展示。"""


def playwright_proxy(url: str | None) -> dict | None:
    """代理 URL → Playwright 代理参数。带凭证的 socks5 不被 Chromium 支持，抛 ValueError。"""
    if url is None:
        return None
    u = urlparse(url)
    if u.scheme not in ("http", "https", "socks5"):
        raise ValueError(f"不支持的代理协议: {u.scheme!r}")
    if not u.hostname or not u.port:
        raise ValueError("代理地址缺少主机或端口")
    if u.scheme == "socks5" and (u.username or u.password):
        raise ValueError("socks5 代理不支持账号密码")
    out = {"server": f"{u.scheme}://{u.hostname}:{u.port}"}
    if u.username:
        out["username"] = unquote(u.username)
        out["password"] = unquote(u.password or "")
    return out


def extract_token(url: str) -> str | None:
    values = parse_qs(urlparse(url).query).get("__token")
    return values[0] if values and values[0] else None


def session_expiry(cookies: list[dict], now: datetime) -> str:
    """取 sid_guard 的过期时间；缺失或无效时为 now + 60 天。"""
    for c in cookies:
        if c.get("name") == "sid_guard" and (c.get("expires") or -1) > 0:
            return datetime.fromtimestamp(c["expires"], UTC).strftime(_ISO_FMT)
    return (now + SESSION_LIFETIME).strftime(_ISO_FMT)


def device_headers_from(raw: dict[str, str]) -> dict[str, str]:
    lower = {k.lower(): v for k, v in raw.items()}
    return {name: lower[name.lower()] for name in _DEVICE_HEADERS if name.lower() in lower}


class LoginCancelled(Exception):
    """用户在扫码完成前关闭了浏览器窗口。"""


async def await_login(
    ctx: Any, page: Any, timeout_s: float
) -> tuple[str, dict[str, str], list[dict]]:
    """在已打开的 context / page 上等待登录成功，返回 (token, 设备头, 完整 cookie 列表)。

    超时抛 TimeoutError；窗口被关闭抛 LoginCancelled。
    """
    loop = asyncio.get_running_loop()
    found: asyncio.Future[tuple[str, dict[str, str]]] = loop.create_future()
    tasks: set[asyncio.Task] = set()  # 持有引用，防止任务被回收

    async def capture(req: Any, token: str) -> None:
        headers = device_headers_from(await req.all_headers())
        # 等请求头期间，别的请求可能已经先完成：这里再判断一次，只取第一个
        if not found.done():
            found.set_result((token, headers))

    def on_request(req: Any) -> None:
        token = extract_token(req.url)
        if token and urlparse(req.url).hostname == _HOST and not found.done():
            task = asyncio.ensure_future(capture(req, token))
            tasks.add(task)
            task.add_done_callback(tasks.discard)

    def on_close(*_: Any) -> None:
        if not found.done():
            found.set_exception(LoginCancelled("浏览器已关闭，扫码登录取消"))

    ctx.on("request", on_request)
    ctx.on("close", on_close)
    try:
        await page.goto(ORDER_PAGE_URL)
    except Exception:
        if found.done() and found.exception() is not None:
            raise found.exception() from None
        raise
    token, headers = await asyncio.wait_for(found, timeout_s)
    try:
        await page.wait_for_load_state("load", timeout=LOAD_WAIT_MS)
    except Exception:  # noqa: BLE001 - 页面没加载完也继续取 cookie
        pass
    return token, headers, await ctx.cookies()


def build_cloak_kwargs(profile_dir: Path, proxy: dict | None) -> dict:
    """CloakBrowser 启动参数。proxy 已由 playwright_proxy() 转成 dict。

    有头模式下不叠加 viewport：CloakBrowser 的屏幕/窗口尺寸由种子派生，
    额外指定 viewport 会破坏 outerWidth >= innerWidth 的自洽性。
    """
    return {
        "user_data_dir": str(profile_dir),
        "headless": False,
        "proxy": proxy,
        "args": cloak_launch_args(get_or_create_seed(profile_dir)),
    }


async def scan_login(
    profile_dir: Path, channel: str, proxy: str | None, timeout_s: int = 300,
    use_cloak: bool = False,
) -> LoginResult:
    """打开订单页等待人工扫码。超时抛 TimeoutError，关窗抛 LoginCancelled。

    use_cloak 为真时走 CloakBrowser 定制 Chromium（每店固定指纹）；
    否则用系统浏览器（channel 指定）。
    """
    playwright_proxy_value = playwright_proxy(proxy)
    if use_cloak:
        try:
            from cloakbrowser import launch_persistent_context_async
        except ImportError as exc:
            raise CloakUnavailable(
                "未安装 cloakbrowser，请先执行：pip install cloakbrowser==0.3.30"
            ) from exc

        ctx = await launch_persistent_context_async(
            **build_cloak_kwargs(profile_dir, playwright_proxy_value),
        )
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            token, headers, cookies = await await_login(ctx, page, timeout_s)
        finally:
            try:
                await ctx.close()
            except Exception:  # noqa: BLE001 - 用户已关窗时 close 会报错
                pass
        return LoginResult(cookies, token, session_expiry(cookies, datetime.now(UTC)), headers)

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            str(profile_dir), channel=channel, headless=False, proxy=playwright_proxy_value,
        )
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            token, headers, cookies = await await_login(ctx, page, timeout_s)
        finally:
            try:
                await ctx.close()
            except Exception:  # noqa: BLE001 - 用户已关窗时 close 会报错
                pass
    return LoginResult(cookies, token, session_expiry(cookies, datetime.now(UTC)), headers)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="手动验证扫码登录（只用测试店或测试代理）")
    ap.add_argument("--profile", type=Path, required=True)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--proxy", help="http(s)://用户:密码@主机:端口")
    group.add_argument("--direct", action="store_true", help="不经代理直连")
    ap.add_argument("--channel", default="msedge" if sys.platform == "win32" else "chrome")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    proxy = None if args.direct else args.proxy
    result = asyncio.run(scan_login(args.profile, args.channel, proxy))
    # 只输出最小摘要：token 前 4 位、cookie 名、UA；不输出任何 cookie 值
    print("token:", result.token[:4] + "…")
    print("cookie 名:", sorted({c["name"] for c in result.cookies}))
    print("User-Agent:", result.device_headers.get("User-Agent"))
    print("expires_at:", result.expires_at)


if __name__ == "__main__":
    main()
