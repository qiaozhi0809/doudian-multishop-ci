"""API 依赖：管理员会话校验。"""

from fastapi import Request

from app.service.auth import NotAuthenticated

COOKIE_NAME = "dd_admin"
COOKIE_MAX_AGE_S = 7 * 24 * 3600
# 不需要登录的接口（backend 5.16）；非 /api/ 路径（前端静态资源）也不校验
PUBLIC_PATHS = frozenset({
    "/api/health", "/api/auth/status", "/api/auth/setup", "/api/auth/login",
})


def require_admin(request: Request) -> str | None:
    """全局依赖：公开接口直接放行；其余 /api/* 必须有有效会话，返回管理员用户名。"""
    path = request.url.path
    if not path.startswith("/api/") or path in PUBLIC_PATHS:
        return None
    username = request.app.state.auth.current_user(request.cookies.get(COOKIE_NAME))
    if username is None:
        raise NotAuthenticated("请先登录")
    return username
