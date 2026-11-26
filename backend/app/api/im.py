"""飞鸽接口：各店消息接收状态、手动重新连接、跨店会话列表与消息记录、在飞鸽中回复。

只读聚合，不提供发送：「在飞鸽中回复」只把该店的浏览器窗口置前并点开会话。

异步端点：接收状态由事件循环里的后台任务维护，在同一个循环里读写。
"""

from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import require_admin
from app.api.im_schemas import (
    ConversationId,
    ImConversation,
    ImConversationPage,
    ImCounts,
    ImFocusResult,
    ImShopStatus,
    ImThread,
)
from app.api.list_sort import ImConversationSort, ImQuick, SortOrder
from app.api.params import parse_shop_ids
from app.domain.errors import InvalidRequest
from app.domain.im_rules import STATE_LABELS
from app.domain.im_view_rules import wait_seconds
from app.service.im_query import ImQueryService
from app.service.im_watcher import ImStatus, ImWatcher
from app.service.shop_admin import ShopAdminService

router = APIRouter(prefix="/api/im", tags=["im"], dependencies=[Depends(require_admin)])

_NOT_ENABLED = "该店未开启接收飞鸽消息"


def _row(shop: Mapping[str, Any], status: ImStatus) -> ImShopStatus:
    return ImShopStatus(
        shop_name=shop["name"], state_label=STATE_LABELS[status.state], **asdict(status))


def _shop_ids(request: Request, raw: str | None) -> list[int]:
    """`shop_ids` 省略 = 全部未停用店铺；给出的编号不存在抛 NotFound。"""
    shops: ShopAdminService = request.app.state.shop_admin
    return shops.target_ids(parse_shop_ids(raw))


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


@router.get("/conversations", response_model=ImConversationPage)
async def list_conversations(
    request: Request,
    shop_ids: str | None = None,
    unread: bool = False,
    quick: ImQuick | None = None,
    sort: ImConversationSort | None = None,
    order: SortOrder = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> ImConversationPage:
    """默认按买家等待时间倒序。只含正在接收的店在内存里的会话。"""
    ids = _shop_ids(request, shop_ids)
    query: ImQueryService = request.app.state.im_query
    now = query.now()
    rows, total = query.conversations(
        ids, unread_only=unread, quick=quick, sort=sort, order=order, page=page,
        page_size=page_size, now=now)
    items = [ImConversation(**asdict(r), wait_seconds=wait_seconds(r, now)) for r in rows]
    return ImConversationPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/conversations/counts", response_model=ImCounts)
async def count_conversations(request: Request, shop_ids: str | None = None) -> ImCounts:
    query: ImQueryService = request.app.state.im_query
    return ImCounts(**query.counts(_shop_ids(request, shop_ids)))


@router.get("/conversations/{shop_id}/{conversation_id}/messages", response_model=ImThread)
async def list_messages(
    shop_id: int, conversation_id: ConversationId, request: Request
) -> ImThread:
    shops: ShopAdminService = request.app.state.shop_admin
    shops.get_view(shop_id)  # 店不存在抛 NotFound
    query: ImQueryService = request.app.state.im_query
    return ImThread(**asdict(query.thread(shop_id, conversation_id)))


@router.post(
    "/conversations/{shop_id}/{conversation_id}/open-in-flybird", response_model=ImFocusResult
)
async def open_in_flybird(
    shop_id: int, conversation_id: ConversationId, request: Request,
    admin: str = Depends(require_admin),
) -> ImFocusResult:
    """排在该店队列里执行；该店没在接收时拒绝。"""
    shops: ShopAdminService = request.app.state.shop_admin
    shops.get_view(shop_id)  # 店不存在抛 NotFound
    im: ImWatcher = request.app.state.im
    return ImFocusResult(result=await im.focus(shop_id, conversation_id, actor=admin))
