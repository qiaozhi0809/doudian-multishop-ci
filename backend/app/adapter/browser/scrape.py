"""借页面读取平台前端可见、但没有稳定接口的固定信息（手动触发，一次即可）。

三类信息的渲染方式不同，因此容错策略也不同：
- 提现卡：支付设置页是服务端渲染，稳定可读
- 店铺ID：店铺管理页，时有时无（微应用懒挂载）
- 主体：资质页是微应用，时有时无

浏览器与扫码同一套环境（有头、viewport 跟随真实窗口、同一指纹种子），只是窗口放到
屏幕外：无头模式的窗口/屏幕尺寸、GPU 路径都和有头不同，同一账号同一 IP 会出现两套设备特征。

任何一项读不到都只是少存一个字段，不影响其它项。
"""

import asyncio
import re
from pathlib import Path

from app.adapter.browser import browser_registry
from app.adapter.browser.browser_registry import BrowserRegistry, Purpose
from app.adapter.browser.login import playwright_proxy

PAYMENT_URL = "https://fxg.jinritemai.com/ffa/ecom/merchant/payment-settings"
SHOP_URL = "https://fxg.jinritemai.com/ffa/grs-new/qualification/common-tools"
QUALIFICATION_URL = "https://fxg.jinritemai.com/ffa/mshop/shop/qualification"
RENDER_WAIT_S = 8
_DIGITS = re.compile(r"\D")
_SHOP_ID = re.compile(r"店铺ID[:：]?\s*(\d+)")

_CLICK_ENTITY_TAB = """() => {
    const els = [...document.querySelectorAll('div,span,a,li,button')]
      .filter(e => (e.textContent || '').includes('主体信息'));
    if (!els.length) return false;
    els.sort((a, b) => a.textContent.length - b.textContent.length);
    let t = els[0];
    for (let i = 0; i < 3 && t.parentElement; i += 1) t = t.parentElement;
    t.click();
    return true;
}"""


def _line_after(lines: list[str], key: str) -> str | None:
    for i, ln in enumerate(lines):
        if ln == key and i + 1 < len(lines) and lines[i + 1]:
            return lines[i + 1]
    return None


def parse_bank_card(text: str) -> dict[str, str]:
    """从支付设置页文本里取开户行与卡号尾号。

    页面形如：
        开户名\\n张三\\n银行卡号\\n6222 **** **** 1234 567\\n开户银行\\n示例银行
    卡号中间被平台打码，去掉非数字后末四位就是真实尾号。
    """
    lines = [ln.strip() for ln in text.splitlines()]
    out: dict[str, str] = {}
    bank_name = _line_after(lines, "开户银行")
    if bank_name:
        out["bank_name"] = bank_name
    raw = _line_after(lines, "银行卡号") or ""
    digits = _DIGITS.sub("", raw)
    if len(digits) >= 4:
        out["bank_tail"] = digits[-4:]
    return out


def parse_shop_id(text: str) -> dict[str, str]:
    m = _SHOP_ID.search(text)
    return {"platform_shop_id": m.group(1)} if m else {}


def parse_entity(text: str) -> dict[str, str]:
    lines = [ln.strip() for ln in text.splitlines()]
    name = _line_after(lines, "公司名称")
    return {"entity": name} if name else {}


async def scrape_platform_info(
    profile_dir: Path, proxy: str | None, *, registry: BrowserRegistry | None = None,
) -> dict[str, str]:
    """依次尝试三类信息，返回读到的字段；失败项直接缺席。

    proxy 是该店出口代理 URL（直连为 None）；浏览器不可用时抛 CloakUnavailable。
    浏览器在登记表里登记（用途 scrape），关闭超时会强杀进程树。
    """
    reg = registry or browser_registry.REGISTRY
    info: dict[str, str] = {}
    async with reg.open_cloak(
        profile_dir, Purpose.SCRAPE, playwright_proxy(proxy), offscreen=True
    ) as ctx:
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        for url, parse in (
            (PAYMENT_URL, parse_bank_card),
            (SHOP_URL, parse_shop_id),
            (QUALIFICATION_URL, parse_entity),
        ):
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                await asyncio.sleep(RENDER_WAIT_S)
                if url == QUALIFICATION_URL:
                    await page.evaluate(_CLICK_ENTITY_TAB)
                    await asyncio.sleep(4)
                text = await page.evaluate("document.body.innerText")
                info.update(parse(text or ""))
            except Exception:  # noqa: BLE001 - 单页失败不影响其它项
                continue
    return info
