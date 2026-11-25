"""对账接口的请求 / 响应模型。"""

from typing import Literal

from pydantic import BaseModel, Field


class ReconcileRunRequest(BaseModel):
    window_days: int | None = Field(default=None, ge=1, le=90)


class ReconcileStarted(BaseModel):
    run_id: str
    status: str
    shop_ids: list[int]
    window_days: int
    started_at: str


class ReconcileRunRow(BaseModel):
    id: int
    run_id: str
    status: str
    shop_ids: list[int]
    window_days: int
    started_at: str
    finished_at: str | None
    scanned: int
    finding_count: int
    error: str | None


class ReconcileFindingRow(BaseModel):
    id: int
    run_id: str
    shop_id: int
    shop_name: str
    shop_order_id: str
    kind: str
    kind_title: str
    local_status: int | None
    platform_status: int | None
    local_tracking_no: str | None
    platform_tracking_no: str | None
    local_company_code: str | None
    platform_company_code: str | None
    detail: str | None
    status: str
    created_at: str
    handled_at: str | None


class ReconcileFindingsPage(BaseModel):
    items: list[ReconcileFindingRow]
    total: int
    page: int
    page_size: int
    run: ReconcileRunRow | None


class ReconcileMarkRequest(BaseModel):
    status: Literal["open", "handled"]
