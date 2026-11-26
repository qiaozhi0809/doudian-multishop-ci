"""「在飞鸽中回复」：经该店队列让常驻页窗口置前并点开会话（adapter/flybird/focus.py）。

买家昵称只用来在页面上定位，不进日志、审计、事件。页面报错的原文带着定位条件（含昵称），
这里只记异常类型，换成固定提示抛出。审计不记会话编号。
"""

from collections.abc import Callable
from typing import Literal

import structlog
from sqlalchemy import Engine

from app.adapter.flybird.focus import focus_conversation
from app.domain.audit import CallRecord
from app.domain.errors import InvalidRequest
from app.service.im_run import Run
from app.service.shop_runner import ShopRunner
from app.store import audit_store

log = structlog.get_logger()

FocusResult = Literal["opened", "not_found"]
NOT_RECEIVING = "该店飞鸽未在接收"
FOCUS_FAILED = "没能在飞鸽中打开该会话，请重试"


async def open_conversation(
    engine: Engine, runner: ShopRunner, shop_id: int, conversation_id: str, *,
    receiving: Callable[[], Run | None], actor: str, now: Callable[[], str],
) -> FocusResult:
    """receiving 返回该店正在接收的那一轮；没有则拒绝。"""

    def current() -> Run:
        if (run := receiving()) is None:
            raise InvalidRequest(NOT_RECEIVING)
        return run

    async def job(_client) -> FocusResult:
        run = current()  # 排队期间页面可能已关
        name = next(
            (v.buyer_name for v in run.session.snapshot()
             if v.conversation_id == conversation_id),
            None,
        )
        try:
            opened = await focus_conversation(run.page.page, name)
        except Exception as e:  # noqa: BLE001
            log.warning("im.focus_failed", shop_id=shop_id, error=type(e).__name__)
            raise InvalidRequest(FOCUS_FAILED) from None
        return "opened" if opened else "not_found"

    def audit(result: str, status: str) -> None:
        record = CallRecord(shop_id, "im.focus", actor, {}, {"result": result}, status, 0)
        with engine.begin() as conn:
            audit_store.insert(conn, record, now())

    current()  # 没在接收的店不进队列
    try:
        result = await runner.run(shop_id, job, actor=actor)
    except Exception:
        audit("error", "error")
        raise
    audit(result, "ok")
    return result
