"""店铺画像同步：登录成功后从平台拉取资质与负责人，落 shop_profile（design/data-model 6.2）。"""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine

from app.adapter.browser.cloak_launch import CloakUnavailable
from app.adapter.browser.scrape import scrape_platform_info
from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.domain.audit import CallRecord
from app.domain.errors import InvalidRequest
from app.domain.shop_profile_rules import clean_scraped
from app.service.shop_runner import ShopRunner
from app.store import audit_store, shop_profile_store, shop_store

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

    async def scrape_card(self, shop_id: int, *, actor: str = "system") -> dict[str, str]:
        """手动触发：用该店已登录的 profile 读平台页面上的固定信息。

        提现卡、店铺ID、主体三类都试一遍，读到哪个存哪个；读不到就留空，
        用户可以在「编辑店铺」里手填。平台没有对应接口，所以是手动按钮而不是
        登录时自动执行——避免每次扫码多等十几秒，也避免页面改版拖垮登录流程。

        和扫码一样经 ShopRunner：出口未就绪、风控暂停、会话失效都在打开浏览器前拦下，
        并进该店串行队列，不会和扫码抢同一个 profile 目录；绝不退回直连。
        """

        async def job(_client: object) -> dict[str, str]:
            try:
                return await scrape_platform_info(
                    self._profiles_dir / str(shop_id), self._runner.proxy_for(shop_id)
                )
            except CloakUnavailable as e:  # 未预下载等：提示本身就是处理办法，原样给用户
                raise InvalidRequest(str(e)) from e
            except ValueError as e:  # 代理地址不受支持（消息不含账号密码）
                raise InvalidRequest(str(e)) from e
            except Exception as e:  # noqa: BLE001 - 浏览器或页面失败都归为可重试的读取失败
                raise InvalidRequest("读取平台信息失败，可稍后重试或手工填写") from e

        try:
            info = await self._runner.run(shop_id, job, actor=actor)
        except Exception as e:
            # 失败也留痕：只记异常类型名，不记消息与值
            self._audit_scrape(shop_id, actor, {"error": type(e).__name__}, "error")
            raise
        # 抓到的值按手工维护的同一规则校验：不合规的丢弃（页面改版可能读到超长或非数字文本）
        cleaned, dropped = clean_scraped(info)
        now = self._clock().strftime(_ISO_FMT)
        profile = {k: v for k, v in cleaned.items() if k != "entity"}
        written = sorted(profile)
        with self._engine.begin() as conn:
            if profile:
                shop_profile_store.patch(conn, shop_id, now, **profile)
            entity = cleaned.get("entity")
            shop = shop_store.get(conn, shop_id)
            if entity and shop is not None and not shop["entity"]:
                # 主体在 shop 表；手填过的不覆盖
                shop_store.update_fields(conn, shop_id, now, entity=entity)
                written = sorted([*written, "entity"])
            # 审计只记实际写入 / 丢弃的字段名，不记值（卡尾号、店铺ID 属于敏感信息）
            resp: dict[str, list[str]] = {"fields": written}
            if dropped:
                resp["dropped"] = dropped
            self._insert_audit(conn, shop_id, actor, resp, "ok", now)
        return cleaned

    def _audit_scrape(self, shop_id: int, actor: str, resp: dict, result: str) -> None:
        with self._engine.begin() as conn:
            self._insert_audit(conn, shop_id, actor, resp, result,
                               self._clock().strftime(_ISO_FMT))

    @staticmethod
    def _insert_audit(conn, shop_id: int, actor: str, resp: dict, result: str, now: str) -> None:
        audit_store.insert(conn, CallRecord(
            shop_id, "shop.profile_scrape", actor, {}, resp, result, 0), now)

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
