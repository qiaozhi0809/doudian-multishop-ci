"""店铺接口的请求与响应模型（前端类型由此生成）。"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

ShopStatus = Literal["active", "needs_login", "disabled"]
Health = Literal["healthy", "expiring", "expired"]
EgressMode = Literal["direct", "proxy"]
EgressState = Literal["unchecked", "ok", "unreachable", "changed", "duplicate"]

# 手工维护字段：这里只去首尾空白，格式由服务层按 domain/shop_profile_rules 校验，
# 这样 422 的 message 是具体的中文原因（schema 的 pattern 报错只有笼统提示）。空串 = 清空。
PlatformShopId = Annotated[str, StringConstraints(strip_whitespace=True)]
BankName = Annotated[str, StringConstraints(strip_whitespace=True)]
BankTail = Annotated[str, StringConstraints(strip_whitespace=True)]


class ShopRow(BaseModel):
    id: int
    name: str
    entity: str | None
    shop_no: str | None
    status: ShopStatus
    health: Health | None
    expires_at: str | None
    paused_reason: str | None
    egress_mode: EgressMode | None
    proxy_display: str | None
    egress_ip: str | None
    egress_ip_pending: str | None
    egress_status: EgressState
    proxy_expires_at: str | None
    ready_for_label: bool
    not_ready_reasons: list[str]
    admin_name: str | None
    shop_name: str | None
    platform_shop_id: str | None
    bank_name: str | None
    bank_tail: str | None
    im_enabled: bool


class ShopCreate(BaseModel):
    name: str
    entity: str | None = None
    shop_no: str | None = Field(
        default=None, description="旧字段，界面已不用；店铺ID 用 platform_shop_id")
    platform_shop_id: PlatformShopId | None = None
    egress: "EgressRequest | None" = None


class ShopPatch(BaseModel):
    name: str | None = None
    entity: str | None = None
    channel: Literal["protocol", "browser"] | None = None
    enabled: bool | None = None
    # 平台侧无稳定接口，允许手工维护（迁移 0010）
    platform_shop_id: PlatformShopId | None = None
    bank_name: BankName | None = None
    bank_tail: BankTail | None = None
    im_enabled: bool | None = None


class EgressRequest(BaseModel):
    mode: EgressMode
    pool_id: int | None = Field(default=None, description="从代理池选择的池项 id")
    proxy_url: str | None = Field(default=None, description="http(s)://账号:密码@主机:端口")
    paste: str | None = Field(default=None, description="代理商格式 IP|端口|账号|密码|到期日")
    expires_at: str | None = None


class EgressStatusOut(BaseModel):
    egress_ip: str | None
    egress_ip_pending: str | None
    egress_status: EgressState


class BaseSummary(BaseModel):
    addresses: int
    couriers: int
    templates: int
    accounts: int
    ready_for_label: bool
    not_ready_reasons: list[str]


class AddressOut(BaseModel):
    address_id: str
    name: str | None
    phone: str | None
    region: str | None
    is_default: bool


class CourierOut(BaseModel):
    courier_code: str
    name: str | None


class TemplateOut(BaseModel):
    template_code: str
    courier_code: str | None
    name: str | None
    is_custom: bool


class AccountOut(BaseModel):
    courier_code: str
    ebill_id: str
    net_code: str
    net_name: str | None
    balance: int | None
    is_default: bool


class BaseData(BaseModel):
    addresses: list[AddressOut]
    couriers: list[CourierOut]
    templates: list[TemplateOut]
    accounts: list[AccountOut]


class Started(BaseModel):
    status: Literal["started"] = "started"
