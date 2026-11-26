"""店铺与会话接口。涉及抖店请求的一律经 ShopRunner。"""

from fastapi import APIRouter, Depends, Request

from app.adapter.doudian import endpoints as ep
from app.api.deps import require_admin
from app.api.shop_schemas import (
    BaseData,
    BaseSummary,
    EgressRequest,
    EgressStatusOut,
    ShopCreate,
    ShopPatch,
    ShopRow,
    Started,
)
from app.domain.errors import InvalidRequest
from app.service.base_data import BaseDataService
from app.service.egress import EgressService
from app.service.shop_admin import ShopAdminService
from app.service.shop_login import ShopLoginFlow
from app.service.shop_runner import ShopRunner

router = APIRouter(prefix="/api/shops", tags=["shops"])


def _state(request: Request):
    return request.app.state


def _row(request: Request, shop_id: int) -> ShopRow:
    admin: ShopAdminService = _state(request).shop_admin
    return ShopRow(**admin.get_view(shop_id))


@router.get("", response_model=list[ShopRow])
def list_shops(request: Request) -> list[ShopRow]:
    return [ShopRow(**v) for v in _state(request).shop_admin.list_view()]


@router.post("", response_model=ShopRow, status_code=201)
def create_shop(
    body: ShopCreate, request: Request, admin: str = Depends(require_admin)
) -> ShopRow:
    try:
        shop_id = _state(request).shop_admin.create(
            body.name, body.entity, body.shop_no,
            egress=body.egress.model_dump() if body.egress else None, actor=admin,
        )
    except ValueError as e:  # 校验信息不含账号密码
        raise InvalidRequest(str(e)) from None
    return _row(request, shop_id)


@router.patch("/{shop_id}", response_model=ShopRow)
def patch_shop(
    shop_id: int, body: ShopPatch, request: Request, admin: str = Depends(require_admin)
) -> ShopRow:
    _state(request).shop_admin.update(
        shop_id, name=body.name, entity=body.entity, channel=body.channel, enabled=body.enabled,
        platform_shop_id=body.platform_shop_id, bank_name=body.bank_name, bank_tail=body.bank_tail,
        actor=admin,
    )
    return _row(request, shop_id)


@router.post("/{shop_id}/profile/scrape", response_model=ShopRow)
async def scrape_profile(
    shop_id: int, request: Request, admin: str = Depends(require_admin)
) -> ShopRow:
    """手动读取平台页面上可见、但没有接口的固定信息：店铺ID、主体、收款账户摘要。"""
    try:
        await _state(request).shop_profile.scrape_card(shop_id)
    except Exception as e:  # noqa: BLE001 - 浏览器或页面失败都归为可重试的读取失败
        raise InvalidRequest("读取平台信息失败，可稍后重试或手工填写") from e
    return _row(request, shop_id)


@router.put("/{shop_id}/egress", response_model=ShopRow)
def set_egress(
    shop_id: int, body: EgressRequest, request: Request, admin: str = Depends(require_admin)
) -> ShopRow:
    egress: EgressService = _state(request).egress
    try:
        egress.set_egress(
            shop_id, body.mode, pool_id=body.pool_id, proxy_url=body.proxy_url, paste=body.paste,
            expires_at=body.expires_at, actor=admin,
        )
    except ValueError as e:  # 校验信息不含账号密码
        raise InvalidRequest(str(e)) from None
    return _row(request, shop_id)


@router.post("/{shop_id}/egress/check", response_model=EgressStatusOut)
async def check_egress(
    shop_id: int, request: Request, accept_change: bool = False,
    admin: str = Depends(require_admin),
) -> EgressStatusOut:
    status = await _state(request).egress.check(shop_id, accept_change=accept_change, actor=admin)
    return EgressStatusOut(
        egress_ip=status.egress_ip, egress_ip_pending=status.egress_ip_pending,
        egress_status=status.egress_status,  # type: ignore[arg-type]
    )


@router.post("/{shop_id}/login", response_model=Started, status_code=202)
async def login_shop(
    shop_id: int, request: Request, admin: str = Depends(require_admin)
) -> Started:
    state = _state(request)
    runner: ShopRunner = state.runner
    flow: ShopLoginFlow = state.login_flow
    await runner.precheck(shop_id, needs_session=False)  # 出口不通 / 暂停：同步报错，不打开浏览器
    state.tasks.spawn(f"login-{shop_id}", flow.login(shop_id, admin))
    return Started()


@router.post("/{shop_id}/probe", response_model=ShopRow)
async def probe_shop(
    shop_id: int, request: Request, admin: str = Depends(require_admin)
) -> ShopRow:
    async def job(client):
        await client.call(ep.TABCNT)

    await _state(request).runner.run(shop_id, job, actor=admin)
    return _row(request, shop_id)


@router.post("/{shop_id}/sync-base", response_model=BaseSummary)
async def sync_base(
    shop_id: int, request: Request, admin: str = Depends(require_admin)
) -> BaseSummary:
    service: BaseDataService = _state(request).base_data
    s = await service.sync(shop_id, admin)
    return BaseSummary(
        addresses=s.addresses, couriers=s.couriers, templates=s.templates, accounts=s.accounts,
        ready_for_label=s.ready_for_label, not_ready_reasons=s.not_ready_reasons,
    )


@router.get("/{shop_id}/base", response_model=BaseData)
def get_base(shop_id: int, request: Request) -> BaseData:
    return BaseData(**_state(request).shop_admin.base_view(shop_id))


@router.post("/{shop_id}/resume", response_model=ShopRow)
def resume_shop(
    shop_id: int, request: Request, admin: str = Depends(require_admin)
) -> ShopRow:
    _state(request).shop_admin.resume(shop_id, admin)
    return _row(request, shop_id)
