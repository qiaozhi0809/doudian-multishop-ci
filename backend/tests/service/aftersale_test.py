import json
from pathlib import Path

import pytest

from app.adapter.doudian.errors import BizRejected
from app.service.aftersale import AftersaleService
from tests.fakes import reply
from tests.service.support import Env

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "m5"


def fx(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def env(engine, tmp_path):
    return Env(engine, tmp_path, responses=[])


def service(env) -> AftersaleService:
    return AftersaleService(env.engine, env.runner)


async def test_sync_stores_rows_and_list_reads_local(env):
    env.transport.responses[:] = [reply(fx("aftersale_list"))]
    (outcome,) = await service(env).sync([env.shop_id], "admin")
    assert (outcome.fetched, outcome.complete, outcome.error) == (2, True, None)
    assert outcome.synced_at is not None

    rows, total = service(env).list_local([env.shop_id])
    assert total == 2
    assert rows[0]["shop_name"] == "店A"
    assert rows[0]["after_sale_id"] == "140000000000000001"  # apply_time 较新，排在前
    assert rows[0]["display"]["status_text"] == "待商家处理"
    assert rows[1]["status_deadline"] is None

    todo, todo_total = service(env).list_local([env.shop_id], open_only=True, by_deadline=True)
    assert todo_total == 1
    assert todo[0]["after_sale_id"] == "140000000000000001"

    body = env.transport.requests[0]["json"]
    assert body["page"] == 1  # 售后列表 1-based
    assert body["conf_version"] == "v13"


async def test_sync_pages_only_when_full(env):
    body = fx("aftersale_list")
    template = body["data"]["items"][0]
    full = json.loads(json.dumps(body))
    full["data"]["items"] = [
        {**template, "after_sale_info": {**template["after_sale_info"],
                                         "after_sale_id": f"id{i}"}}
        for i in range(50)
    ]
    short = json.loads(json.dumps(body))
    short["data"]["items"] = [{**template, "after_sale_info": {
        **template["after_sale_info"], "after_sale_id": "last"}}]
    env.transport.responses[:] = [reply(full), reply(short)]

    (outcome,) = await service(env).sync([env.shop_id], "admin")
    assert (outcome.fetched, outcome.complete) == (51, True)
    assert [r["json"]["page"] for r in env.transport.requests] == [1, 2]


async def test_counts_upstream_and_failure_isolation(env):
    env.transport.responses[:] = [reply(fx("aftersale_counts"))]
    (result,) = await service(env).counts([env.shop_id], "admin")
    assert result.source == "upstream"
    assert result.pending_total == 2  # all_audit 1 + return_for_receive 1
    assert result.fetched_at is not None
    assert "all_audit" in env.transport.requests[0]["params"]["fields"]

    env.transport.responses[:] = [BizRejected("100021", "售后数据不可用")]
    (failed,) = await service(env).counts([env.shop_id], "admin")
    assert failed.source == "error"
    assert failed.counts is None
    assert failed.error and "售后数据不可用" in failed.error


async def test_detail_fetches_upstream(env):
    env.transport.responses[:] = [reply(fx("aftersale_detail"))]
    detail = await service(env).detail(env.shop_id, "140000000000000001", "admin")
    assert detail["title_info"]["title"] == "退货退款"
    assert len(detail["progress_node"]) == 2
    params = env.transport.requests[0]["params"]
    assert params["after_sale_id"] == "140000000000000001"
    assert params["aftersale_platform_source"] == "fxg"
