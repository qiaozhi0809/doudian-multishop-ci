"""扫码登录编排：出口代理 → 扫码 → 保存会话 → 探测 → 同步基础数据。失败发 shop_login_failed。"""

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import structlog

from app.adapter.browser.browser_registry import BrowserRegistry
from app.adapter.browser.browser_timing import SCAN_WAIT_S
from app.adapter.browser.login import CloakUnavailable, LoginCancelled, LoginResult, scan_login
from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.errors import DoudianError
from app.domain.errors import NotFound
from app.service.base_data import BaseDataService
from app.service.egress import EgressConflict, EgressNotReady
from app.service.events import SHOP_LOGIN_FAILED, EventBus
from app.service.session_manager import SessionManager
from app.service.shop_runner import ShopPaused, ShopRunner

log = structlog.get_logger()

if TYPE_CHECKING:
    from app.service.shop_profile import ShopProfileService


class ScanFn(Protocol):
    """注入点：与 scan_login 同签名的扫码函数，测试可替换。"""

    def __call__(
        self, profile_dir: Path, channel: str, proxy: str | None, timeout_s: int = ...,
        use_cloak: bool = ..., *, registry: BrowserRegistry | None = ...,
    ) -> Awaitable[LoginResult]: ...


# 让出该店资料目录（关掉常驻页）；返回是否真的关了一个
YieldProfile = Callable[[int], Awaitable[bool]]

SCAN_TIMEOUT_S = SCAN_WAIT_S  # 扫码浏览器最长存活由它推导（browser_timing.login_max_age）
_USER_FACING = (DoudianError, EgressNotReady, EgressConflict, ShopPaused, NotFound,
                LoginCancelled, CloakUnavailable)


class ShopLoginFlow:
    def __init__(
        self, runner: ShopRunner, sessions: SessionManager, base_data: BaseDataService,
        events: EventBus, profiles_dir: Path, channel: str,
        scan: ScanFn = scan_login, timeout_s: int = SCAN_TIMEOUT_S,
        use_cloak: bool = False, profile: "ShopProfileService | None" = None,
        browsers: BrowserRegistry | None = None, yield_profile: YieldProfile | None = None,
    ) -> None:
        self._browsers = browsers
        self._yield_profile = yield_profile
        self._runner = runner
        self._sessions = sessions
        self._base_data = base_data
        self._events = events
        self._profiles_dir = profiles_dir
        self._channel = channel
        self._scan = scan
        self._timeout_s = timeout_s
        self._use_cloak = use_cloak
        self._profile = profile

    async def login(self, shop_id: int, actor: str) -> None:
        try:
            await self._runner.run(shop_id, self._scan_job(shop_id), actor=actor,
                                   needs_session=False)
            # 扫码任务已释放该店队列，探测与基础数据同步各自重新入队
            await self._runner.run(shop_id, _probe, actor=actor)
            await self._sync_profile(shop_id)
            await self._base_data.sync(shop_id, actor)
        except Exception as e:
            self._events.publish(SHOP_LOGIN_FAILED, {"shop_id": shop_id, "reason": _reason(e)})
            raise

    async def _sync_profile(self, shop_id: int) -> None:
        """店铺画像 best-effort：拉不到不影响登录，只是列表里少显示负责人。"""
        if self._profile is None:
            return
        try:
            await self._profile.sync(shop_id)
        except Exception as e:  # noqa: BLE001 - 画像失败不该让扫码登录失败
            log.warning("shop_profile.sync_failed", shop_id=shop_id, error=type(e).__name__)

    def _scan_job(self, shop_id: int) -> Callable[[FxgClient], Awaitable[None]]:
        async def job(_client: FxgClient) -> None:
            if self._yield_profile is not None:  # 已在该店队列里，让出后不会被别的任务插队
                await self._yield_profile(shop_id)
            profile = self._profiles_dir / str(shop_id)
            profile.mkdir(parents=True, exist_ok=True)
            proxy = self._runner.proxy_for(shop_id)  # 扫码浏览器必须走该店出口
            result = await self._scan(
                profile, self._channel, proxy, self._timeout_s, use_cloak=self._use_cloak,
                registry=self._browsers)
            self._sessions.save_login(shop_id, result)

        return job


async def _probe(client: FxgClient) -> None:
    await client.call(ep.TABCNT)


def _reason(e: Exception) -> str:
    if isinstance(e, TimeoutError):
        return "扫码超时，请重新发起登录"
    if isinstance(e, _USER_FACING):
        return str(e) or type(e).__name__
    log.error("shop_login.unexpected", error=type(e).__name__)
    return "登录失败，请查看日志"
