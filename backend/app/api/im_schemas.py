"""飞鸽接口的响应模型（前端类型由此生成）。"""

from pydantic import BaseModel

from app.domain.im_rules import ImState


class ImShopStatus(BaseModel):
    shop_id: int
    shop_name: str
    state: ImState
    state_label: str
    since: str
    next_retry_at: str | None
    last_error: str | None
