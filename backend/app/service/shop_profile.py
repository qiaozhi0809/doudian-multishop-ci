"""店铺画像同步：登录成功后从平台拉取资质与负责人，落 shop_profile（design/data-model 6.2）。"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine

from app.adapter.browser.scrape import scrape_platform_info
from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.service.shop_runner import ShopRunner
from app.store import shop_profile_store

_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
_RAW_LIMIT = 20_000  # raw_json 只留摘要够排查，防止异常响应撑爆库


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ShopProfileService:
    """best-effort：同步失败不应让扫码登录整体失败，由调用方兜住异常。"""

    def __init__(
        self, engine: Engine, runner: ShopRunner, *, profiles_dir: Path,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._engine = engine
        self._runner = runner
        self._profiles_dir = profiles_dir
        self._clock = clock or _utc_now

    async def scrape_card(self, shop_id: int) -> dict[str, str]:
        """手动触发：用该店已登录的 profile 读平台页面上的固定信息。

        提现卡、店铺ID、主体三类都试一遍，读到哪个存哪个；读不到就留空，
        用户可以在「编辑店铺」里手填。平台没有对应接口，所以是手动按钮而不是
        登录时自动执行——避免每次扫码多等十几秒，也避免页面改版拖垮登录流程。
        """
        info = await scrape_platform_info(
            self._profiles_dir / str(shop_id), self._runner.proxy_for(shop_id)
        )
        if info:
            with self._engine.begin() as conn:
                shop_profile_store.patch(
                    conn, shop_id, self._clock().strftime(_ISO_FMT), **info
                )
        return info

    async def sync(self, shop_id: int) -> dict:
        async def job(client: FxgClient) -> dict:
            return {
                "shop_info": await client.call(ep.SHOP_INFO),
                "shop_admin": await client.call(ep.SHOP_ADMIN),
            }

        payload = await self._runner.run(shop_id, job, actor="system")
        self._save(shop_id, payload)
        return payload

    def _save(self, shop_id: int, payload: dict) -> None:
        info = (payload.get("shop_info") or {}).get("data") or {}
        admin = (payload.get("shop_admin") or {}).get("data") or {}
        settle = (info.get("shop_settle_day") or {}).get("delay_day_display")
        with self._engine.begin() as conn:
            shop_profile_store.upsert(
                conn,
                shop_id,
                self._clock().strftime(_ISO_FMT),
                qual_id=info.get("qual_id"),
                shop_name=info.get("shop_name"),
                shop_type=info.get("shop_type"),
                operate_status_str=info.get("operate_status_str"),
                open_time=info.get("shop_open_time_str"),
                settle_delay=settle,
                admin_name=admin.get("shop_charge_name"),
                admin_mobile=admin.get("shop_charge_mobile"),
                raw_json=json.dumps(payload, ensure_ascii=False)[:_RAW_LIMIT],
            )
