"""基础数据同步：快递公司 → 发货地址 → 面单模板 → 面单账户（只拉模板里出现的快递）。"""

from dataclasses import dataclass
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy import Engine

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient
from app.adapter.doudian.parsers import (
    parse_addresses,
    parse_couriers,
    parse_ebill_accounts,
    parse_templates,
)
from app.domain.base_data_rules import account_usable, compute_readiness
from app.domain.models import AddressDTO, CourierDTO, EbillAccountDTO, TemplateDTO
from app.service.events import SYNC_PROGRESS, EventBus
from app.service.shop_runner import ShopRunner
from app.store import base_data_store

MAX_ADDRESS_PAGES = 20  # 防止平台分页异常时死循环
_ISO_FMT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class BaseDataSummary:
    addresses: int
    couriers: int
    templates: int
    accounts: int
    ready_for_label: bool
    not_ready_reasons: list[str]


@dataclass(frozen=True)
class _Fetched:
    couriers: list[CourierDTO]
    addresses: list[AddressDTO]
    templates: list[TemplateDTO]
    accounts: list[EbillAccountDTO]


async def _fetch_all_addresses(client: FxgClient) -> list[AddressDTO]:
    out: list[AddressDTO] = []
    for page in range(1, MAX_ADDRESS_PAGES + 1):  # 该接口 page 从 1 起
        rows = parse_addresses(await client.call(ep.ADDRESS_LIST, params={"page": page}))
        out.extend(rows)
        if len(rows) < ep.ADDRESS_PAGE_SIZE:
            break
    return out


async def _fetch_all(client: FxgClient) -> _Fetched:
    couriers = parse_couriers(await client.call(ep.EXPRESS_LIST))
    addresses = await _fetch_all_addresses(client)
    templates = parse_templates(await client.call(ep.TEMPLATE_LIST))
    template_couriers = list(dict.fromkeys(t.courier_code for t in templates if t.courier_code))
    accounts: list[EbillAccountDTO] = []
    for code in template_couriers:
        resp = await client.call(ep.EBILL_ACCOUNTS, params={"company": code})
        accounts.extend(parse_ebill_accounts(resp, code))
    return _Fetched(couriers, addresses, templates, accounts)


class BaseDataService:
    def __init__(self, engine: Engine, runner: ShopRunner, events: EventBus) -> None:
        self._engine = engine
        self._runner = runner
        self._events = events

    async def sync(self, shop_id: int, actor: str) -> BaseDataSummary:
        """全部拉取成功后才在一个事务里替换本地行；任一步失败，本地旧数据保持不变。"""
        fetched = await self._runner.run(shop_id, _fetch_all, actor=actor)
        now = datetime.now(UTC).strftime(_ISO_FMT)
        with self._engine.begin() as conn:
            base_data_store.replace_couriers(conn, shop_id, fetched.couriers, now)
            base_data_store.replace_addresses(conn, shop_id, fetched.addresses, now)
            base_data_store.replace_templates(conn, shop_id, fetched.templates, now)
            base_data_store.replace_ebill_accounts(conn, shop_id, fetched.accounts, now)
            ready, reasons = self.readiness(conn, shop_id)
        summary = BaseDataSummary(
            len(fetched.addresses), len(fetched.couriers), len(fetched.templates),
            len(fetched.accounts), ready, reasons,
        )
        self._events.publish(SYNC_PROGRESS, {
            "shop_id": shop_id, "kind": "base", "addresses": summary.addresses,
            "couriers": summary.couriers, "templates": summary.templates,
            "accounts": summary.accounts, "ready_for_label": ready,
            "not_ready_reasons": reasons,
        })
        return summary

    @staticmethod
    def readiness(conn: sa.Connection, shop_id: int) -> tuple[bool, list[str]]:
        addresses = base_data_store.list_addresses(conn, shop_id)
        templates = base_data_store.list_templates(conn, shop_id)
        accounts = base_data_store.list_ebill_accounts(conn, shop_id)
        return compute_readiness(
            has_default_address=any(a["is_default"] for a in addresses),
            template_couriers={t["courier_code"] for t in templates if t["courier_code"]},
            usable_account_couriers={
                a["courier_code"] for a in accounts if account_usable(a["balance"])
            },
        )
