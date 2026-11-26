"""飞鸽接口：各店消息接收状态、手动重新连接。只读聚合，不提供发送。

异步端点：接收状态由事件循环里的后台任务维护，在同一个循环里读写。
"""

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import require_admin
from app.api.im_schemas import ImShopStatus
from app.domain.errors import InvalidRequest
from app.domain.im_rules import STATE_LABELS
from app.service.im_watcher import ImStatus, ImWatcher
from app.service.shop_admin import ShopAdminService

router = APIRouter(prefix="/api/im", tags=["im"], dependencies=[Depends(require_admin)])

_NOT_ENABLED = "该店未开启接收飞鸽消息"


def _row(shop: Mapping[str, Any], status: ImStatus) -> ImShopStatus:
    return ImShopStatus(
        shop_name=shop["name"], state_label=STATE_LABELS[status.state], **asdict(status))


@router.get("/status", response_model=list[ImShopStatus])
async def list_status(request: Request) -> list[ImShopStatus]:
    admin: ShopAdminService = request.app.state.shop_admin
    im: ImWatcher = request.app.state.im
    return [_row(s, im.status(s["id"])) for s in admin.list_view() if s["im_enabled"]]


@router.post("/shops/{shop_id}/restart", response_model=ImShopStatus)
async def restart(
    shop_id: int, request: Request, admin: str = Depends(require_admin)
) -> ImShopStatus:
    """手动「重新连接」：不等页面打开，返回当前状态（排队中 / 启动中等）。"""
    shops: ShopAdminService = request.app.state.shop_admin
    shop = shops.get_view(shop_id)  # 店不存在抛 NotFound
    if not shop["im_enabled"]:
        raise InvalidRequest(_NOT_ENABLED)
    im: ImWatcher = request.app.state.im
    return _row(shop, await im.restart(shop_id, actor=admin))
