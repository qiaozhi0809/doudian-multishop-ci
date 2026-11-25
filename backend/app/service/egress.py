"""每店固定独立出口（backend 5.17）：设置、检查、就绪判断、取代理。

代理 URL（含账号密码）只以 SecretBox 密文落库；日志与异常信息只出现 主机:端口。
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
import structlog
from sqlalchemy import Engine

from app.adapter.doudian.errors import EgressUnavailable
from app.domain.audit import CallRecord
from app.domain.egress_rules import (
    display_proxy,
    expiry_state,
    judge_egress,
    parse_provider_line,
    proxy_identity,
    validate_proxy_url,
)
from app.domain.errors import NotFound
from app.service.egress_probe import FetchIp
from app.service.events import SHOP_STATUS_CHANGED, EventBus
from app.service.session_manager import ACTIVE, DISABLED, NEEDS_LOGIN
from app.shared.secret_box import SecretBox
from app.store import audit_store, proxy_pool_store, shop_store

log = structlog.get_logger()

MODES = ("direct", "proxy")
READY_CACHE = timedelta(minutes=10)
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
_PROXY_MISSING = "该店铺代理地址缺失，请重新设置出口"


class EgressNotReady(Exception):
    """出口未配置、IP 变化未确认、IP 重复或代理已到期。"""


class EgressConflict(Exception):
    """已有另一家启用店铺使用直连。"""


class ProxyPoolInUse(EgressConflict):
    """池项已被另一家启用店铺绑定。"""

    def __init__(self, shop_name: str, message: str | None = None) -> None:
        super().__init__(message or f"代理已被店铺「{shop_name}」使用")


@dataclass(frozen=True)
class EgressStatus:
    egress_ip: str | None
    egress_ip_pending: str | None
    egress_status: str


def reset_shop_egress(conn: sa.Connection, shop: Mapping[str, Any], now: str) -> str:
    """换出口后的复位：清已确认 IP、状态 unchecked；已登录店铺转 needs_login。返回新状态。"""
    shop_store.set_egress(
        conn, shop["id"], now, egress_ip=None, egress_ip_pending=None,
        egress_status="unchecked", egress_checked_at=None)
    if shop["status"] == ACTIVE:
        shop_store.set_status(conn, shop["id"], NEEDS_LOGIN, now)
        return NEEDS_LOGIN
    return shop["status"]


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
        self, shop_id: int, mode: str, pool_id: int | None = None,
        proxy_url: str | None = None, paste: str | None = None,
        expires_at: str | None = None, actor: str = "system",
    ) -> None:
        """改出口（开事务调 bind_in，提交后发事件）。"""
        now = self._clock().strftime(_ISO_FMT)
        try:
            with self._engine.begin() as conn:
                shop = shop_store.get(conn, shop_id)
                if shop is None:
                    raise NotFound(f"店铺不存在: {shop_id}", shop_id)
                new_status = self.bind_in(
                    conn, shop, mode=mode, pool_id=pool_id, proxy_url=proxy_url,
                    paste=paste, expires_at=expires_at, now=now, actor=actor)
        except sa.exc.IntegrityError:
            if mode == "proxy":  # 预检之后被抢先：uq_shop_pool 兜底
                raise ProxyPoolInUse("另一家店铺") from None
            raise EgressConflict("已有另一家启用店铺使用直连") from None
        self._events.publish(SHOP_STATUS_CHANGED, {
            "shop_id": shop_id, "status": new_status, "egress_status": "unchecked",
        })

    def bind_in(
        self, conn: sa.Connection, shop: Mapping[str, Any], *, mode: str,
        pool_id: int | None, proxy_url: str | None, paste: str | None,
        expires_at: str | None, now: str, actor: str,
    ) -> str:
        """在调用方的事务内：校验入口 → 解析/入池 → 绑定 → 复位出口 → 审计。返回新店铺状态。

        不发事件（由调用方在提交后发）；唯一索引冲突以 IntegrityError 向上抛。
        """
        if mode not in MODES:
            raise ValueError(f"出口方式只能是 {' / '.join(MODES)}")
        if sum(x is not None and x != "" for x in (pool_id, proxy_url, paste)) > 1:
            raise ValueError("pool_id、proxy_url、paste 最多给一个")
        display: str | None = None
        bound_pool_id: int | None = None
        if mode == "direct":
            if pool_id is not None or proxy_url or paste:
                raise ValueError("直连不需要代理地址")
            self._ensure_no_other_direct(conn, shop)
        elif pool_id is not None:
            item = proxy_pool_store.get(conn, pool_id)
            if item is None:
                raise NotFound(f"代理池项不存在: {pool_id}")
            if expiry_state(item["expires_at"], self._parse_now(now)) == "expired":
                raise ValueError("代理已到期，请续费或更换")
            bound_pool_id, display = pool_id, item["proxy_display"]
            self._ensure_pool_free(conn, pool_id, shop["id"])
        else:
            url, expiry = self._resolve_url(proxy_url, paste, expires_at)
            display = display_proxy(url)
            bound_pool_id = proxy_pool_store.upsert(
                conn, identity=proxy_identity(url), proxy_url=self._box.encrypt(url.encode()),
                proxy_display=display, expires_at=expiry, now=now,
            )
            self._ensure_pool_free(conn, bound_pool_id, shop["id"])
        shop_store.set_egress(conn, shop["id"], now, egress_mode=mode, proxy_pool_id=bound_pool_id)
        new_status = reset_shop_egress(conn, shop, now)
        # 审计只记方式与 主机:端口，绝不记代理 URL
        audit_store.insert(conn, CallRecord(
            shop["id"], "shop.set_egress", actor,
            {"mode": mode, "proxy_display": display},
            {"status": new_status}, "ok", 0), now)
        return new_status

    @staticmethod
    def _parse_now(now: str) -> datetime:
        return datetime.strptime(now, _ISO_FMT).replace(tzinfo=UTC)

    @staticmethod
    def _resolve_url(
        proxy_url: str | None, paste: str | None, expires_at: str | None
    ) -> tuple[str, str | None]:
        expiry = expires_at
        if paste:
            url, paste_expiry = parse_provider_line(paste)
            expiry = expires_at or paste_expiry
        elif proxy_url:
            url = proxy_url.strip()
        else:
            raise ValueError("代理模式需要提供代理池项或代理地址")
        errors = validate_proxy_url(url)
        if errors:
            raise ValueError("；".join(errors))
        return url, expiry

    @staticmethod
    def _ensure_pool_free(conn: sa.Connection, pool_id: int, shop_id: int) -> None:
        for other in proxy_pool_store.referrers(conn, pool_id):
            if other["id"] != shop_id and other["status"] != DISABLED:
                raise ProxyPoolInUse(other["name"])

    @staticmethod
    def _ensure_no_other_direct(conn: sa.Connection, shop: Any) -> None:
        for other in shop_store.list(conn):
            if (other["id"] != shop["id"] and other["egress_mode"] == "direct"
                    and other["status"] != DISABLED):
                raise EgressConflict(f"店铺「{other['name']}」已使用直连，最多一家店可直连")

    # ---- 检查 ----

    async def check(
        self, shop_id: int, accept_change: bool = False, actor: str = "system"
    ) -> EgressStatus:
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
            if accept_change:
                audit_store.insert(conn, CallRecord(
                    shop_id, "shop.accept_egress_change", actor,
                    {"proxy_display": shop["proxy_display"] or "direct"},
                    {"egress_status": verdict}, "ok", 0), now_iso)
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
            raise NotFound(f"店铺不存在: {shop_id}", shop_id)
        return shop

    @staticmethod
    def _require_usable(shop: Any, now: datetime) -> None:
        if shop["egress_mode"] is None:
            raise EgressNotReady("该店铺尚未配置出口")
        if shop["egress_mode"] == "proxy" and not shop["proxy_url"]:
            raise EgressNotReady(_PROXY_MISSING)
        if expiry_state(shop["proxy_expires_at"], now) == "expired":
            raise EgressNotReady("代理已到期，请续费或更换")
