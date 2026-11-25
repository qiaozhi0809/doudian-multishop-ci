"""会话管理：加密保存登录结果、取出凭证、标记失效。同步方法（本机 SQLite，写入很短）。"""

import json
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Engine

from app.adapter.browser.login import LoginResult
from app.adapter.doudian.client import ShopCredentials
from app.adapter.doudian.errors import SessionExpired
from app.domain.errors import NotFound
from app.domain.session_health import health_from_expiry
from app.service.events import SHOP_STATUS_CHANGED, EventBus
from app.shared.secret_box import SecretBox
from app.store import session_store, shop_store
from app.store.session_store import SessionRow

ACTIVE = "active"
NEEDS_LOGIN = "needs_login"
DISABLED = "disabled"
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"
_INACTIVE_MESSAGES = {
    NEEDS_LOGIN: "该店铺需要重新扫码登录",
    DISABLED: "该店铺已停用",
}


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SessionManager:
    def __init__(
        self, engine: Engine, box: SecretBox, events: EventBus,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._engine = engine
        self._box = box
        self._events = events
        self._clock = clock

    @property
    def events(self) -> EventBus:
        return self._events

    def save_login(self, shop_id: int, result: LoginResult) -> None:
        now = self._clock()
        now_iso = now.strftime(_ISO_FMT)
        row = SessionRow(
            shop_id=shop_id,
            cookies_blob=self._box.encrypt(json.dumps(result.cookies).encode()),
            token_blob=self._box.encrypt(result.token.encode()),
            device_json=json.dumps(result.device_headers),
            expires_at=result.expires_at,
        )
        with self._engine.begin() as conn:
            if shop_store.get(conn, shop_id) is None:
                raise NotFound(f"店铺不存在: {shop_id}", shop_id)
            session_store.save(conn, row, now_iso)
            shop_store.set_status(conn, shop_id, ACTIVE, now_iso)
        self._events.publish(SHOP_STATUS_CHANGED, {
            "shop_id": shop_id, "status": ACTIVE,
            "health": health_from_expiry(result.expires_at, now),
        })

    def get_credentials(self, shop_id: int) -> ShopCredentials:
        with self._engine.connect() as conn:
            shop = shop_store.get(conn, shop_id)
            row = session_store.load(conn, shop_id)
        if shop is None:
            raise SessionExpired("店铺不存在")
        if shop["status"] != ACTIVE:
            raise SessionExpired(_INACTIVE_MESSAGES.get(shop["status"], "该店铺当前不可用"))
        if row is None:
            raise SessionExpired("该店铺需要重新扫码登录")
        return ShopCredentials(
            shop_id=shop_id,
            cookies=json.loads(self._box.decrypt(row.cookies_blob)),
            token=self._box.decrypt(row.token_blob).decode(),
            device_headers=json.loads(row.device_json),
        )

    def mark_expired(self, shop_id: int) -> None:
        with self._engine.begin() as conn:
            shop_store.set_status(conn, shop_id, NEEDS_LOGIN, self._clock().strftime(_ISO_FMT))
        self._events.publish(SHOP_STATUS_CHANGED, {
            "shop_id": shop_id, "status": NEEDS_LOGIN, "health": "expired",
        })
