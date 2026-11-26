"""飞鸽已读拦截：适配器里唯一允许拦截的模块（docs/api/flybird.md §4，所有者裁定「不标已读」）。

只做两件事：页面加载前注入脚本，丢弃标记已读、输入状态两种上行帧；
中止页面兜底用的 HTTP 已读请求。不改写、不伪造任何帧或响应。
"""

import json
from pathlib import Path

from playwright.async_api import BrowserContext, Route

from app.adapter.flybird import endpoints as ep

SCRIPT_PATH = Path(__file__).with_name("read_guard.js")
_CONFIG_PLACEHOLDER = "__READ_GUARD_CONFIG__"

_blocked = 0


def render_script() -> str:
    """把 endpoints 里的常量填进注入脚本。"""
    config = {
        "wsHost": ep.WS_HOST,
        "dropCmds": sorted(ep.DROP_CMDS),
        "payloadField": ep.FRAME_PAYLOAD,
        "cmdField": ep.PAYLOAD_CMD,
    }
    template = SCRIPT_PATH.read_text(encoding="utf-8")
    return template.replace(_CONFIG_PLACEHOLDER, json.dumps(config))


def blocked_count() -> int:
    """本进程中止过的已读请求数（不记 URL，参数里有签名）。"""
    return _blocked


async def _abort(route: Route) -> None:
    global _blocked
    await route.abort()
    _blocked += 1


async def install(context: BrowserContext) -> None:
    """必须在页面打开工作台之前调用；失败就抛错。"""
    await context.add_init_script(script=render_script())
    # 结尾用 **：单个 * 不跨斜杠，查询串里的签名带 / 时会漏掉已读请求
    await context.route("**" + ep.MARK_READ_PATH + "**", _abort)
