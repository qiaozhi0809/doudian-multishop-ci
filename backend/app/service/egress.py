"""每店固定独立出口（backend 5.17）：设置、检查、就绪判断、取代理。

代理 URL（含账号密码）只以 SecretBox 密文落库；日志与异常信息只出现 主机:端口。
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy import Engine

from app.adapter.doudian.errors import EgressUnavailable
from app.domain.egress_rules import (
    display_proxy,
    expiry_state,
    judge_egress,
    parse_provider_line,
    validate_proxy_url,
)
from app.service.egress_probe import FetchIp
from app.service.events import SHOP_STATUS_CHANGED, EventBus
from app.service.session_manager import ACTIVE, DISABLED, NEEDS_LOGIN
from app.shared.secret_box import SecretBox
from app.store import shop_store

log = structlog.get_logger()

MODES = ("direct", "proxy")
READY_CACHE = timedelta(minutes=10)
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
_PROXY_MISSING = "该店铺代理地址缺失，请重新设置出口"


class EgressNotReady(Exception):
    """出口未配置、IP 变化未确认、IP 重复或代理已到期。"""


class EgressConflict(Exception):
    """已有另一家启用店铺使用直连。"""


@dataclass(frozen=True)
class EgressStatus:
    egress_ip: str | None
    egress_ip_pending: str | None
    egress_status: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _age_key(shop: Any) -> tuple[str, int]:
    """谁建得早：created_at 相同时按 id。"""
    return (shop["created_at"], shop["id"])


class EgressService:
    def __init__(
        self, engine: Engine, box: SecretBox, events: EventBus, fetch_ip: FetchIp,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._engine = engine
        self._box = box
        self._events = events
        self._fetch_ip = fetch_ip
        self._clock = clock

    # ---- 设置 ----

    def set_egress(
        self, shop_id: int, mode: str, proxy_url: str | None = None,
        paste: str | None = None, expires_at: str | None = None,
    ) -> None:
        """改出口：清空已确认的 IP、状态复位；已登录的店铺转 needs_login，必须重新扫码。"""
        if mode not in MODES:
            raise ValueError(f"出口方式只能是 {' / '.join(MODES)}")
        url, expiry = None, expires_at
        if mode == "proxy":
            if paste:
                url, paste_expiry = parse_provider_line(paste)
                expiry = expires_at or paste_expiry
            elif proxy_url:
                url = proxy_url.strip()
            else:
                raise ValueError("代理模式需要提供代理地址")
            errors = validate_proxy_url(url)
            if errors:
                raise ValueError("；".join(errors))
        elif proxy_url or paste:
            raise ValueError("直连不需要代理地址")

        now = self._clock().strftime(_ISO_FMT)
        try:
            with self._engine.begin() as conn:
                shop = shop_store.get(conn, shop_id)
                if shop is None:
                    raise LookupError(f"店铺不存在: {shop_id}")
                if mode == "direct":
                    self._ensure_no_other_direct(conn, shop)
                shop_store.set_egress(
                    conn, shop_id, now, egress_mode=mode,
                    proxy_url=self._box.encrypt(url.encode()) if url else None,
                    proxy_display=display_proxy(url) if url else None,
                    egress_ip=None, egress_status="unchecked", egress_checked_at=None,
                    egress_ip_pending=None, proxy_expires_at=expiry,
                )
                new_status = shop["status"]
                if shop["status"] == ACTIVE:
                    new_status = NEEDS_LOGIN
                    shop_store.set_status(conn, shop_id, NEEDS_LOGIN, now)
        except sa.exc.IntegrityError:
            raise EgressConflict("已有另一家启用店铺使用直连") from None
        self._events.publish(SHOP_STATUS_CHANGED, {
            "shop_id": shop_id, "status": new_status, "egress_status": "unchecked",
        })

    @staticmethod
    def _ensure_no_other_direct(conn: sa.Connection, shop: Any) -> None:
        for other in shop_store.list(conn):
            if (other["id"] != shop["id"] and other["egress_mode"] == "direct"
                    and other["status"] != DISABLED):
                raise EgressConflict(f"店铺「{other['name']}」已使用直连，最多一家店可直连")

    # ---- 检查 ----

    async def check(self, shop_id: int, accept_change: bool = False) -> EgressStatus:
        """经该店出口取 IP 并判定。只有 ok 才写 egress_ip；accept_change 把新 IP 转正。"""
        now = self._clock()
        shop = self._load(shop_id)
        self._require_usable(shop, now)
        ip = await self._fetch_ip(self.proxy_for(shop_id))
        now_iso = self._clock().strftime(_ISO_FMT)
        changed: dict[int, str] = {}  # shop_id -> 新的 egress_status
        with self._engine.begin() as conn:
            shop = shop_store.get(conn, shop_id)
            others = [
                o for o in shop_store.list(conn)
                if o["id"] != shop_id and o["status"] != DISABLED and o["egress_ip"]
            ]
            current = None if accept_change else shop["egress_ip"]
            verdict = judge_egress(current, ip, {o["egress_ip"] for o in others})
            if verdict == "duplicate":
                clash = [o for o in others if o["egress_ip"] == ip]
                if all(_age_key(o) > _age_key(shop) for o in clash):
                    # 本店建得更早：让后建的店让位，本店保留这个 IP
                    for o in clash:
                        shop_store.set_egress(
                            conn, o["id"], now_iso, egress_ip=None, egress_ip_pending=ip,
                            egress_status="duplicate", egress_checked_at=now_iso,
                        )
                        changed[o["id"]] = "duplicate"
                    verdict = judge_egress(current, ip, set())
            fields: dict[str, Any] = {"egress_status": verdict, "egress_checked_at": now_iso}
            if verdict == "ok":
                fields.update(egress_ip=ip, egress_ip_pending=None)
            elif verdict in ("changed", "duplicate"):
                fields.update(egress_ip_pending=ip)
            shop_store.set_egress(conn, shop_id, now_iso, **fields)
            result = EgressStatus(
                fields.get("egress_ip", shop["egress_ip"]),
                fields.get("egress_ip_pending", shop["egress_ip_pending"]),
                verdict,
            )
        changed[shop_id] = verdict
        log.info("egress.checked", shop_id=shop_id, verdict=verdict,
                 proxy_display=shop["proxy_display"] or "direct")
        for sid, status in changed.items():
            self._events.publish(SHOP_STATUS_CHANGED, {"shop_id": sid, "egress_status": status})
        return result

    async def ensure_ready(self, shop_id: int) -> None:
        """每轮任务开始前调用：10 分钟内 ok 直接通过；否则重查。不通抛 EgressUnavailable。"""
        now = self._clock()
        shop = self._load(shop_id)
        self._require_usable(shop, now)
        checked = shop["egress_checked_at"]
        if shop["egress_status"] == "ok" and checked and (
            now - datetime.strptime(checked, _ISO_FMT).replace(tzinfo=UTC) < READY_CACHE
        ):
            return
        status = (await self.check(shop_id)).egress_status
        if status == "ok":
            return
        if status == "unreachable":
            raise EgressUnavailable("出口不可达，请检查代理是否到期或更换代理")
        raise EgressNotReady(f"出口状态异常: {status}")

    def mark_unreachable(self, shop_id: int) -> None:
        """请求过程中出口断了：写 unreachable，使 ensure_ready 的 10 分钟缓存失效。"""
        with self._engine.begin() as conn:
            shop_store.set_egress(
                conn, shop_id, self._clock().strftime(_ISO_FMT), egress_status="unreachable"
            )
        self._events.publish(
            SHOP_STATUS_CHANGED, {"shop_id": shop_id, "egress_status": "unreachable"}
        )

    # ---- 取代理 ----

    def proxy_for(self, shop_id: int) -> str | None:
        """解密后的代理 URL；直连或未配置返回 None。"""
        shop = self._load(shop_id)
        if shop["egress_mode"] == "proxy" and not shop["proxy_url"]:
            raise EgressNotReady(_PROXY_MISSING)  # 绝不把「缺代理」当成直连
        blob = shop["proxy_url"]
        return self._box.decrypt(blob).decode() if blob else None

    # ---- 内部 ----

    def _load(self, shop_id: int) -> Any:
        with self._engine.connect() as conn:
            shop = shop_store.get(conn, shop_id)
        if shop is None:
            raise LookupError(f"店铺不存在: {shop_id}")
        return shop

    @staticmethod
    def _require_usable(shop: Any, now: datetime) -> None:
        if shop["egress_mode"] is None:
            raise EgressNotReady("该店铺尚未配置出口")
        if shop["egress_mode"] == "proxy" and not shop["proxy_url"]:
            raise EgressNotReady(_PROXY_MISSING)
        if expiry_state(shop["proxy_expires_at"], now) == "expired":
            raise EgressNotReady("代理已到期，请续费或更换")
