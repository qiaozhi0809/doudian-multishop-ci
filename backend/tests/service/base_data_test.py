import json
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.adapter.doudian.errors import BizRejected
from app.adapter.doudian.transport import TransportResponse
from app.service.base_data import BaseDataService
from tests.fakes import reply
from tests.service.support import Env

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "doudian"


def fx(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def as_response(body: dict) -> TransportResponse:
    return reply(body)


def happy_responses() -> list:
    return [as_response(fx(n)) for n in ("express_list", "address_list", "template_list",
                                         "ebill_accounts")]


@pytest.fixture
def env(engine, tmp_path):
    return Env(engine, tmp_path, responses=happy_responses())


def make_service(env) -> BaseDataService:
    return BaseDataService(env.engine, env.runner, env.events)


def count(env, table):
    with env.engine.connect() as conn:
        return conn.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar()


async def test_sync_counts(env):
    summary = await make_service(env).sync(env.shop_id, "admin")
    counts = (summary.addresses, summary.couriers, summary.templates, summary.accounts)
    assert counts == (1, 1, 2, 1)
    assert summary.ready_for_label is True and summary.not_ready_reasons == []
    assert [count(env, t) for t in ("shop_address", "courier", "waybill_template",
                                    "ebill_account")] == [1, 1, 2, 1]
    paths = [r["url"].rsplit("/", 1)[1] for r in env.transport.requests]
    assert paths == ["expressList", "getAfterSaleList", "searchTemplates",
                     "getEbillAccountListByExpress"]


async def test_address_paging_starts_at_one(env):
    first = fx("address_list")
    template_row = first["data"]["address_list"][0]
    first["data"]["address_list"] = [
        {**template_row, "id": i, "is_send_default": 1 if i == 1 else 0} for i in range(1, 501)
    ]
    second = fx("address_list")
    second["data"]["address_list"] = [{**template_row, "id": 9001, "is_send_default": 0}]
    env.transport.responses[:] = [
        as_response(fx("express_list")), as_response(first), as_response(second),
        as_response(fx("template_list")), as_response(fx("ebill_accounts")),
    ]
    summary = await make_service(env).sync(env.shop_id, "admin")
    assert summary.addresses == 501
    pages = [r["params"]["page"] for r in env.transport.requests[1:3]]
    assert pages == [1, 2]
    assert env.transport.requests[1]["params"]["pageSize"] == 500


async def test_accounts_only_for_template_couriers(env):
    express = fx("express_list")
    express["data"]["eBills"].append({**express["data"]["eBills"][0], "company": "sf"})
    env.transport.responses[:] = [
        as_response(express), as_response(fx("address_list")),
        as_response(fx("template_list")), as_response(fx("ebill_accounts")),
    ]
    summary = await make_service(env).sync(env.shop_id, "admin")
    assert summary.couriers == 2
    account_requests = [r for r in env.transport.requests if "Ebill" in r["url"]]
    assert [r["params"]["company"] for r in account_requests] == ["jd"]


async def test_not_ready_without_default_address(env):
    addresses = fx("address_list")
    addresses["data"]["address_list"][0]["is_send_default"] = 0
    env.transport.responses[1] = as_response(addresses)
    summary = await make_service(env).sync(env.shop_id, "admin")
    assert summary.ready_for_label is False
    assert summary.not_ready_reasons == ["没有默认发货地址"]


async def test_zero_balance_account_not_ready(env):
    accounts = fx("ebill_accounts")
    accounts["data"]["accounts"][0]["balance"] = 0
    env.transport.responses[3] = as_response(accounts)
    summary = await make_service(env).sync(env.shop_id, "admin")
    assert summary.ready_for_label is False and summary.accounts == 1


async def test_ready_with_one_complete_courier(env):
    templates = fx("template_list")
    group = templates["data"]["list"][0]
    templates["data"]["list"].append({**group, "companyCode": "sf", "customTempList": [
        {**group["customTempList"][0], "customTempCode": "C_sf"}], "parentTempList": [],
        "publicTempList": []})
    sf_accounts = fx("ebill_accounts")
    sf_accounts["data"]["accounts"][0].update(balance=0, eBillId=2)
    env.transport.responses[:] = [
        as_response(fx("express_list")), as_response(fx("address_list")),
        as_response(templates), as_response(sf_accounts), as_response(fx("ebill_accounts")),
    ]
    # 第一个账户请求（jd）余额为 0，第二个（sf）月结可用 → 仍就绪
    first_jd = fx("ebill_accounts")
    first_jd["data"]["accounts"][0]["balance"] = 0
    env.transport.responses[3] = as_response(first_jd)
    summary = await make_service(env).sync(env.shop_id, "admin")
    assert summary.ready_for_label is True and summary.accounts == 2


async def test_failure_keeps_old_rows(env):
    svc = make_service(env)
    await svc.sync(env.shop_id, "admin")
    env.transport.responses[:] = [
        as_response(fx("express_list")), as_response(fx("address_list")),
        reply({"code": 602500705, "msg": "bad"}),  # 模板接口失败
    ]
    with pytest.raises(BizRejected):
        await svc.sync(env.shop_id, "admin")
    assert [count(env, t) for t in ("shop_address", "courier", "waybill_template",
                                    "ebill_account")] == [1, 1, 2, 1]


async def test_failure_on_first_sync_writes_nothing(env):
    env.transport.responses[:] = [
        as_response(fx("express_list")), as_response(fx("address_list")),
        as_response(fx("template_list")), reply({"code": 602500705, "msg": "bad"}),
    ]
    with pytest.raises(BizRejected):
        await make_service(env).sync(env.shop_id, "admin")
    assert count(env, "courier") == 0 and count(env, "shop_address") == 0


async def test_publishes_sync_progress(env):
    sub = env.events.subscribe()
    await make_service(env).sync(env.shop_id, "admin")
    events = []
    while len(events) < 1:
        events.append(await sub.__anext__())
    event, data = events[-1]
    assert event == "sync_progress"
    assert data["shop_id"] == env.shop_id and data["kind"] == "base"
    assert data["ready_for_label"] is True and data["templates"] == 2


async def test_readiness_reads_stored_rows(env):
    svc = make_service(env)
    with env.engine.connect() as conn:
        assert svc.readiness(conn, env.shop_id)[0] is False  # 还没同步过
    await svc.sync(env.shop_id, "admin")
    with env.engine.connect() as conn:
        assert svc.readiness(conn, env.shop_id) == (True, [])
