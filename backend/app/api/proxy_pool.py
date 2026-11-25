"""代理池接口：导入、列表、编辑、删除、手动检测。响应不含代理账号密码。"""

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import require_admin
from app.api.proxy_pool_schemas import (
    PoolCheckOut,
    PoolImportFailure,
    PoolImportIn,
    PoolImportOut,
    PoolItem,
    PoolPatch,
)
from app.domain.errors import InvalidRequest
from app.service.proxy_pool import ProxyPoolService

router = APIRouter(prefix="/api/proxy-pool", tags=["proxy-pool"])


def _state(request: Request):
    return request.app.state


def _svc(request: Request) -> ProxyPoolService:
    return _state(request).proxy_pool


def _item(request: Request, pool_id: int) -> PoolItem:
    return PoolItem(**next(v for v in _svc(request).list_view() if v["id"] == pool_id))


@router.get("", response_model=list[PoolItem])
def list_pool(request: Request) -> list[PoolItem]:
    return [PoolItem(**v) for v in _svc(request).list_view()]


@router.post("/import", response_model=PoolImportOut)
def import_pool(
    body: PoolImportIn, request: Request, admin: str = Depends(require_admin)
) -> PoolImportOut:
    try:
        s = _svc(request).import_text(body.text, admin)
    except ValueError as e:
        raise InvalidRequest(str(e)) from None
    return PoolImportOut(
        added=s.added, skipped=s.skipped, failed=s.failed,
        failures=[PoolImportFailure(line=n, reason=r) for n, r in s.failures])


@router.patch("/{pool_id}", response_model=PoolItem)
def patch_pool(
    pool_id: int, body: PoolPatch, request: Request, admin: str = Depends(require_admin)
) -> PoolItem:
    try:
        _svc(request).update(
            pool_id, host=body.host, port=body.port, username=body.username,
            password=body.password, expires_at=body.expires_at, actor=admin)
    except ValueError as e:  # 校验信息不含账号密码
        raise InvalidRequest(str(e)) from None
    return _item(request, pool_id)


@router.delete("/{pool_id}", status_code=204)
def delete_pool(pool_id: int, request: Request, admin: str = Depends(require_admin)) -> Response:
    _svc(request).delete(pool_id, admin)
    return Response(status_code=204)


@router.post("/{pool_id}/check", response_model=PoolCheckOut)
async def check_pool(
    pool_id: int, request: Request, admin: str = Depends(require_admin)
) -> PoolCheckOut:
    r = await _svc(request).check(pool_id, admin)
    return PoolCheckOut(
        ip=r.ip, reason=r.reason, elapsed_ms=r.elapsed_ms, ip_in_use_by=r.ip_in_use_by)
