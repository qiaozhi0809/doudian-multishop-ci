"""代理池接口的请求与响应模型（前端类型由此生成）。"""

from typing import Literal

from pydantic import BaseModel

ExpiryState = Literal["ok", "expiring", "expired"]
CheckReason = Literal["timeout", "proxy_unavailable", "network", "bad_echo"]


class ShopRef(BaseModel):
    shop_id: int
    shop_name: str


class PoolItem(BaseModel):
    id: int
    proxy_display: str
    expires_at: str | None
    expiry_state: ExpiryState
    in_use_by: ShopRef | None
    last_checked_at: str | None
    last_check_ip: str | None


class PoolImportIn(BaseModel):
    text: str


class PoolImportFailure(BaseModel):
    line: int
    reason: str


class PoolImportOut(BaseModel):
    added: int
    skipped: int
    failed: int
    failures: list[PoolImportFailure]


class PoolPatch(BaseModel):
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    expires_at: str | None = None


class PoolCheckOut(BaseModel):
    ip: str | None
    reason: CheckReason | None
    elapsed_ms: int
    ip_in_use_by: ShopRef | None
