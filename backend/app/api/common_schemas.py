"""跨接口共用的响应模型。"""

from typing import Any

from pydantic import BaseModel


class Health(BaseModel):
    status: str


class ErrorBody(BaseModel):
    type: str
    message: str
    shop_id: int | None = None
    detail: Any = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody
