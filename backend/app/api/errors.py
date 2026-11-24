"""异常 → 错误信封 {"error": {"type", "message", "shop_id", "detail"}}。"""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.adapter.doudian.errors import (
    BizRejected,
    EgressUnavailable,
    ParseError,
    RiskBlocked,
    SessionExpired,
    TransientError,
)
from app.service.auth import (
    AccountLocked,
    AlreadyInitialized,
    InvalidCredentials,
    NotAuthenticated,
    PasswordRejected,
)
from app.service.egress import EgressConflict, EgressNotReady
from app.service.shop_runner import ShopPaused

log = structlog.get_logger()

# 具体的异常类放前面（先匹配）
STATUS_BY_ERROR: list[tuple[type[Exception], int]] = [
    (NotAuthenticated, 401),
    (InvalidCredentials, 401),
    (AccountLocked, 423),
    (AlreadyInitialized, 409),
    (PasswordRejected, 422),
    (SessionExpired, 409),
    (EgressNotReady, 409),
    (EgressConflict, 409),
    (ShopPaused, 409),
    (RiskBlocked, 429),
    (BizRejected, 422),
    (EgressUnavailable, 503),
    (TransientError, 503),
    (ParseError, 502),
    (LookupError, 404),
]


def envelope(
    type_: str, message: str, status: int, shop_id: int | None = None, detail: Any = None
) -> JSONResponse:
    body = {"error": {"type": type_, "message": message, "shop_id": shop_id, "detail": detail}}
    return JSONResponse(body, status_code=status)


def _domain_error(_: Request, exc: Exception) -> JSONResponse:
    status = next(code for cls, code in STATUS_BY_ERROR if isinstance(exc, cls))
    detail = {"problems": exc.problems} if isinstance(exc, PasswordRejected) else None
    return envelope(type(exc).__name__, str(exc), status, getattr(exc, "shop_id", None), detail)


def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    detail = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
    return envelope("ValidationError", "请求参数不合法", 422, detail=detail)


def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return envelope("HTTPError", str(exc.detail), exc.status_code)


def _unexpected(_: Request, exc: Exception) -> JSONResponse:
    log.error("api.unhandled", error=type(exc).__name__)
    return envelope("InternalError", "服务内部错误", 500)


def install_error_handlers(app: FastAPI) -> None:
    for cls, _ in STATUS_BY_ERROR:
        app.add_exception_handler(cls, _domain_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected)
