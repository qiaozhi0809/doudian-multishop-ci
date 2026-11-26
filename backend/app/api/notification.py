"""通知接口：列表、铃铛汇总 / 顶部横条、已读（通知中心 6.4）。

同步端点：FastAPI 在线程池里执行，库操作不阻塞事件循环。
"""

from fastapi import APIRouter, Query, Request, Response

from app.api.notification_schemas import NotificationItem, NotificationPage, NotificationSummary
from app.domain.errors import NotFound

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPage)
def list_notifications(
    request: Request, unread: bool = False, page: int = Query(1, ge=1),
) -> NotificationPage:
    data = request.app.state.notifications.list(unread_only=unread, page=page)
    return NotificationPage(
        items=[NotificationItem.model_validate(i) for i in data["items"]],
        total=data["total"], page=data["page"], page_size=data["page_size"],
    )


@router.get("/summary", response_model=NotificationSummary)
def summary(request: Request) -> NotificationSummary:
    return NotificationSummary.model_validate(request.app.state.notifications.summary())


@router.post("/read-all", status_code=204)
def read_all(request: Request) -> Response:
    request.app.state.notifications.mark_all_read()
    return Response(status_code=204)


@router.post("/{notification_id}/read", status_code=204)
def read_one(request: Request, notification_id: int) -> Response:
    if not request.app.state.notifications.mark_read(notification_id):
        raise NotFound(f"通知不存在: {notification_id}")
    return Response(status_code=204)
