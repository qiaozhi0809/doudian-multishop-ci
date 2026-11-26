"""店铺管理：列表视图、新增、修改、解除暂停、基础数据查看。不发任何抖店请求。"""

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import Engine

from app.domain.audit import CallRecord
from app.domain.errors import InvalidRequest, NotFound
from app.domain.session_health import health_from_expiry
from app.domain.shop_profile_rules import validate_profile
from app.service.base_data import BaseDataService
from app.service.egress import EgressConflict, EgressService, ProxyPoolInUse
from app.service.events import SHOP_STATUS_CHANGED, EventBus
from app.service.session_manager import ACTIVE, DISABLED, NEEDS_LOGIN
from app.store import audit_store, base_data_store, session_store, shop_profile_store, shop_store

_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
CHANNELS = ("protocol", "browser")
MAX_NAME_LENGTH = 100
REENABLE_CONFLICT = "该店铺的出口与其他启用店铺冲突（直连或代理已被占用），请先更换出口"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ShopAdminService:
    def __init__(
        self, engine: Engine, events: EventBus, egress: EgressService,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._engine = engine
        self._events = events
        self._egress = egress
        self._clock = clock

    # ---- 查询 ----

    def list_view(self) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            return [self._view(conn, s) for s in shop_store.list(conn)]

    def get_view(self, shop_id: int) -> dict[str, Any]:
        with self._engine.connect() as conn:
            return self._view(conn, self._get(conn, shop_id))

    def target_ids(self, shop_ids: Sequence[int] | None) -> list[int]:
        """None = 全部未停用店铺；显式给出的编号必须都存在。"""
        with self._engine.connect() as conn:
            shops = shop_store.list(conn)
            if shop_ids is None:
                return [s["id"] for s in shops if s["status"] != DISABLED]
            known = {s["id"] for s in shops}
            missing = [i for i in shop_ids if i not in known]
            if missing:
                raise NotFound(f"店铺不存在: {missing[0]}", missing[0])
            return list(shop_ids)

    def runnable_ids(self, shop_ids: Sequence[int]) -> list[int]:
        """其中状态为 active 且未暂停的店铺。"""
        with self._engine.connect() as conn:
            return [
                i for i in shop_ids
                if (s := shop_store.get(conn, i)) and s["status"] == ACTIVE
                and not s["paused_reason"]
            ]

    def base_view(self, shop_id: int) -> dict[str, Any]:
        with self._engine.connect() as conn:
            self._get(conn, shop_id)
            return {
                "addresses": [
                    {k: a[k] for k in ("address_id", "name", "phone", "region", "is_default")}
                    | {"is_default": bool(a["is_default"])}
                    for a in base_data_store.list_addresses(conn, shop_id)
                ],
                "couriers": [
                    {"courier_code": c["courier_code"], "name": c["name"]}
                    for c in base_data_store.list_couriers(conn, shop_id)
                ],
                "templates": [
                    {"template_code": t["template_code"], "courier_code": t["courier_code"],
                     "name": t["name"], "is_custom": bool(t["is_custom"])}
                    for t in base_data_store.list_templates(conn, shop_id)
                ],
                "accounts": [
                    {"courier_code": a["courier_code"], "ebill_id": a["ebill_id"],
                     "net_code": a["net_code"], "net_name": a["net_name"],
                     "balance": a["balance"], "is_default": bool(a["is_default"])}
                    for a in base_data_store.list_ebill_accounts(conn, shop_id)
                ],
            }

    # ---- 修改 ----

    def create(
        self, name: str, entity: str | None = None, shop_no: str | None = None,
        egress: Mapping[str, Any] | None = None, actor: str = "system",
        platform_shop_id: str | None = None,
    ) -> int:
        """新增店铺；店铺ID 与带 egress 时的出口绑定都在同一事务内，失败则店铺也不创建。"""
        name = self._valid_name(name)
        shop_ref = self._valid_profile("platform_shop_id", platform_shop_id or "")
        now = self._now()
        new_status: str | None = None
        try:
            with self._engine.begin() as conn:
                sid = shop_store.create(conn, name, now, entity=entity, shop_no=shop_no)
                if shop_ref is not None:
                    shop_profile_store.patch(conn, sid, now, platform_shop_id=shop_ref)
                if egress is not None:
                    shop = self._get(conn, sid)
                    new_status = self._egress.bind_in(
                        conn, shop, mode=egress["mode"], pool_id=egress.get("pool_id"),
                        proxy_url=egress.get("proxy_url"), paste=egress.get("paste"),
                        expires_at=egress.get("expires_at"), now=now, actor=actor)
        except sa.exc.IntegrityError:
            if egress is None:
                raise
            if egress["mode"] == "proxy":
                raise ProxyPoolInUse("另一家店铺") from None
            raise EgressConflict("已有另一家启用店铺使用直连") from None
        if new_status is not None:
            self._events.publish(SHOP_STATUS_CHANGED, {
                "shop_id": sid, "status": new_status, "egress_status": "unchecked",
            })
        return sid

    def update(
        self, shop_id: int, *, name: str | None = None, entity: str | None = None,
        channel: str | None = None, enabled: bool | None = None,
        platform_shop_id: str | None = None, bank_name: str | None = None,
        bank_tail: str | None = None, im_enabled: bool | None = None, actor: str = "system",
    ) -> None:
        fields: dict[str, Any] = {}
        if name is not None:
            fields["name"] = self._valid_name(name)
        if entity is not None:
            fields["entity"] = entity.strip() or None  # 空串 = 清空
        if channel is not None:
            if channel not in CHANNELS:
                raise InvalidRequest(f"通道只能是 {' / '.join(CHANNELS)}")
            fields["channel"] = channel
        profile_fields = {
            key: self._valid_profile(key, value)
            for key, value in (
                ("platform_shop_id", platform_shop_id),
                ("bank_name", bank_name),
                ("bank_tail", bank_tail),
            )
            if value is not None
        }
        if im_enabled is not None:
            fields["im_enabled"] = int(im_enabled)
        now = self._now()
        new_status: str | None = None
        try:
            with self._engine.begin() as conn:
                shop = self._get(conn, shop_id)
                im_changed = "im_enabled" in fields and fields["im_enabled"] != shop["im_enabled"]
                old_profile = shop_profile_store.get(conn, shop_id) or {}
                shop_store.update_fields(conn, shop_id, now, **fields)
                if profile_fields:
                    shop_profile_store.patch(conn, shop_id, now, **profile_fields)
                # 手工改主体 / 店铺ID / 收款信息留痕：只记改了哪些字段名，不记值（敏感）
                edited = sorted(
                    [k for k, v in profile_fields.items() if old_profile.get(k) != v]
                    + (["entity"] if "entity" in fields and fields["entity"] != shop["entity"]
                       else [])
                )
                if edited:
                    self._audit(conn, shop_id, "shop.profile_edit", actor, now, {"fields": edited})
                if enabled is False and shop["status"] != DISABLED:
                    shop_store.set_status(conn, shop_id, DISABLED, now)
                    new_status = DISABLED
                    self._audit(conn, shop_id, "shop.disable", actor, now)
                elif enabled is True and shop["status"] == DISABLED:
                    # 停用期间出口 IP 可能已被别家占用：复位出口检查，重新扫码
                    shop_store.set_egress(
                        conn, shop_id, now, egress_ip=None, egress_ip_pending=None,
                        egress_status="unchecked", egress_checked_at=None)
                    shop_store.set_status(conn, shop_id, NEEDS_LOGIN, now)
                    new_status = NEEDS_LOGIN
                    self._audit(conn, shop_id, "shop.enable", actor, now)
        except sa.exc.IntegrityError:
            raise EgressConflict(REENABLE_CONFLICT) from None
        if new_status is not None or im_changed:  # 飞鸽常驻页靠这个事件开停
            self._events.publish(SHOP_STATUS_CHANGED, {
                "shop_id": shop_id, "status": new_status or shop["status"],
                "egress_status": "unchecked"
                if new_status == NEEDS_LOGIN else shop["egress_status"],
            })

    def resume(self, shop_id: int, actor: str = "system") -> None:
        """人工解除风控暂停。"""
        now = self._now()
        with self._engine.begin() as conn:
            shop = self._get(conn, shop_id)
            shop_store.set_paused(conn, shop_id, None, now)
            self._audit(conn, shop_id, "shop.resume", actor, now,
                        {"previous_reason": shop["paused_reason"]})
        self._events.publish(SHOP_STATUS_CHANGED, {
            "shop_id": shop_id, "status": shop["status"], "paused_reason": None,
        })

    def _audit(
        self, conn: sa.Connection, shop_id: int, action: str, actor: str, now: str,
        req: dict[str, Any] | None = None,
    ) -> None:
        audit_store.insert(conn, CallRecord(
            shop_id, action, actor, req or {}, {}, "ok", 0), now)

    # ---- 内部 ----

    def _now(self) -> str:
        return self._clock().strftime(_ISO_FMT)

    @staticmethod
    def _valid_name(name: str) -> str:
        name = name.strip()
        if not name or len(name) > MAX_NAME_LENGTH:
            raise InvalidRequest(f"店铺名称需为 1~{MAX_NAME_LENGTH} 个字符")
        return name

    @staticmethod
    def _valid_profile(key: str, value: str) -> str | None:
        """去首尾空白；空串 = 清空（None）；格式不符抛 InvalidRequest。"""
        return validate_profile(key, value)

    @staticmethod
    def _get(conn: sa.Connection, shop_id: int) -> Mapping[str, Any]:
        shop = shop_store.get(conn, shop_id)
        if shop is None:
            raise NotFound(f"店铺不存在: {shop_id}", shop_id)
        return shop

    def _view(self, conn: sa.Connection, shop: Mapping[str, Any]) -> dict[str, Any]:
        session = session_store.load(conn, shop["id"])
        expires_at = session.expires_at if session else None
        ready, reasons = BaseDataService.readiness(conn, shop["id"])
        profile = shop_profile_store.get(conn, shop["id"])
        return {
            "id": shop["id"], "name": shop["name"], "status": shop["status"],
            "entity": shop["entity"], "shop_no": shop["shop_no"],
            "health": health_from_expiry(expires_at, self._clock()) if session else None,
            "expires_at": expires_at, "paused_reason": shop["paused_reason"],
            "egress_mode": shop["egress_mode"], "proxy_display": shop["proxy_display"],
            "egress_ip": shop["egress_ip"], "egress_ip_pending": shop["egress_ip_pending"],
            "egress_status": shop["egress_status"], "proxy_expires_at": shop["proxy_expires_at"],
            "ready_for_label": ready, "not_ready_reasons": reasons,
            "admin_name": (profile or {}).get("admin_name"),
            "shop_name": (profile or {}).get("shop_name"),
            "platform_shop_id": (profile or {}).get("platform_shop_id"),
            "bank_name": (profile or {}).get("bank_name"),
            "bank_tail": (profile or {}).get("bank_tail"),
            "im_enabled": bool(shop["im_enabled"]),
        }

