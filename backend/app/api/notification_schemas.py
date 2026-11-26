"""通知接口的响应模型（通知中心 6.4）。"""

from pydantic import BaseModel

from app.domain.notification_rules import Kind, Level


class NotificationItem(BaseModel):
    id: int
    kind: Kind
    level: Level
    shop_id: int | None
    title: str
    body: str | None
    link: str | None
    count: int
    state_key: str | None
    resolved_at: str | None
    read_at: str | None
    created_at: str
    updated_at: str


class NotificationPage(BaseModel):
    items: list[NotificationItem]
    total: int
    page: int
    page_size: int


class StrongOpenShop(BaseModel):
    """一店一行：该店所有未解决的强状态。"""

    shop_id: int
    shop_name: str
    kinds: list[Kind]
    link: str | None


class NotificationSummary(BaseModel):
    unread: int
    strong_open: list[StrongOpenShop]
