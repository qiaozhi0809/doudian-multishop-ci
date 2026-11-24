"""本机管理员登录接口。"""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from app.api.deps import COOKIE_MAX_AGE_S, COOKIE_NAME, require_admin
from app.service.auth import AuthService, NotAuthenticated

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Credentials(BaseModel):
    username: str
    password: str


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


class AuthStatus(BaseModel):
    setup_required: bool
    logged_in: bool
    username: str | None


def _auth(request: Request) -> AuthService:
    return request.app.state.auth


@router.get("/status", response_model=AuthStatus)
def status(request: Request) -> AuthStatus:
    auth = _auth(request)
    username = auth.current_user(request.cookies.get(COOKIE_NAME))
    return AuthStatus(
        setup_required=not auth.is_initialized(), logged_in=username is not None,
        username=username,
    )


@router.post("/setup", response_model=AuthStatus, status_code=201)
def setup(body: Credentials, request: Request) -> AuthStatus:
    """创建管理员。不自动登录，需再调用登录接口。"""
    _auth(request).setup(body.username, body.password)
    return AuthStatus(setup_required=False, logged_in=False, username=None)


@router.post("/login", response_model=AuthStatus)
def login(body: Credentials, request: Request, response: Response) -> AuthStatus:
    token = _auth(request).login(body.username, body.password)
    _set_cookie(response, token)
    return AuthStatus(setup_required=False, logged_in=True, username=body.username)


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    _auth(request).logout(request.cookies.get(COOKIE_NAME))
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "ok"}


@router.post("/password")
def change_password(
    body: ChangePassword, request: Request, _admin: str | None = Depends(require_admin)
) -> dict[str, str]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise NotAuthenticated("请先登录")
    _auth(request).change_password(token, body.old_password, body.new_password)
    return {"status": "ok"}


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME, token, max_age=COOKIE_MAX_AGE_S, path="/", httponly=True, samesite="strict",
    )
