"""借页面读取平台前端可见、但没有稳定接口的固定信息（手动触发，一次即可）。"""

import asyncio
import os
import re
from pathlib import Path

PAYMENT_URL = "https://fxg.jinritemai.com/ffa/ecom/merchant/payment-settings"
RENDER_WAIT_S = 8
_DIGITS = re.compile(r"\D")


def parse_bank_card(text: str) -> dict[str, str]:
    """从支付设置页文本里取开户行与卡号尾号；取不到就返回空字典。

    页面形如：
        开户名\n张三\n银行卡号\n6222 **** **** 1234 567\n开户银行\n示例银行
    卡号中间被平台打码，去掉非数字后末四位就是真实尾号。
    """
    lines = [ln.strip() for ln in text.splitlines()]
    out: dict[str, str] = {}
    for i, ln in enumerate(lines):
        if ln == "开户银行" and i + 1 < len(lines) and lines[i + 1]:
            out["bank_name"] = lines[i + 1]
        if ln == "银行卡号" and i + 1 < len(lines):
            digits = _DIGITS.sub("", lines[i + 1])
            if len(digits) >= 4:
                out["bank_tail"] = digits[-4:]
    return out


async def scrape_bank_card(profile_dir: Path, proxy: object | None) -> dict[str, str]:
    """打开支付设置页读提现卡。失败抛异常，由调用方兜住。"""
    from cloakbrowser import launch_persistent_context_async

    from app.shared.cloak import cloak_launch_args, get_or_create_seed

    ctx = await launch_persistent_context_async(
        os.fspath(profile_dir),
        headless=True,
        viewport=None,
        proxy=proxy,
        args=cloak_launch_args(get_or_create_seed(profile_dir)),
    )
    try:
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(PAYMENT_URL, wait_until="domcontentloaded", timeout=45_000)
        await asyncio.sleep(RENDER_WAIT_S)
        text = await page.evaluate("document.body.innerText")
    finally:
        try:
            await ctx.close()
        except Exception:  # noqa: BLE001 - 页面已关闭时 close 会报错
            pass
    return parse_bank_card(text or "")
