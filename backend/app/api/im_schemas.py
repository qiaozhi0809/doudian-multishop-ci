"""飞鸽接口的响应模型与路径参数（前端类型由此生成）。

买家昵称与消息正文只经这些响应返回给管理员，不进日志。
"""

from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.domain.im_rules import ImState

# 会话 short ID：只放行字母数字与少数分隔符
ConversationId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_:.\-]{1,128}$")]


class ImShopStatus(BaseModel):
    shop_id: int
    shop_name: str
    state: ImState
    state_label: str
    since: str
    next_retry_at: str | None
    last_error: str | None


class ImFocusResult(BaseModel):
    """「在飞鸽中回复」的结果；not_found = 飞鸽会话列表里没定位到唯一的会话。"""

    result: Literal["opened", "not_found"]


class ImConversation(BaseModel):
    shop_id: int
    shop_name: str
    conversation_id: str
    buyer: str
    preview: str
    unread: int
    last_at: str | None
    waiting_since: str | None
    wait_seconds: int | None


class ImConversationPage(BaseModel):
    items: list[ImConversation]
    total: int
    page: int
    page_size: int


class ImCounts(BaseModel):
    """计数卡：字段名与 quick 参数的取值一一对应。"""

    unread: int
    waiting: int
    overdue: int
    today: int


class ImMessage(BaseModel):
    message_id: str
    sender_role: Literal["buyer", "agent", "robot", "platform"]
    text: str
    sent_at: str


class ImThread(BaseModel):
    shop_id: int
    conversation_id: str
    items: list[ImMessage]
