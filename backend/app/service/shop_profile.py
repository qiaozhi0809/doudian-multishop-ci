"""店铺画像同步：登录成功后从平台拉取资质与负责人，落 shop_profile（design/data-model 6.2）。"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine

from app.adapter.browser.scrape import scrape_bank_card
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
        """手动触发：用该店已登录的 profile 读提现卡，只存开户行与尾号。

        平台无对应接口（数据由服务端渲染进页面），因此这一步是手动按钮而不是
        登录时自动执行——避免每次扫码多等十几秒，也避免页面改版拖垮登录流程。
        """
        card = await scrape_bank_card(
            self._profiles_dir / str(shop_id), self._runner.proxy_for(shop_id)
        )
        if card:
            with self._engine.begin() as conn:
                shop_profile_store.patch(
                    conn, shop_id, self._clock().strftime(_ISO_FMT), **card
                )
        return card

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
