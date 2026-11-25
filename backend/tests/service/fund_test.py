import json
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.service.fund import FundService
from tests.fakes import reply
from tests.service.support import Env

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "m5"
SHOP_NO = "62000070001"


def fx(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def env(engine, tmp_path):
    return Env(engine, tmp_path, responses=[])


def service(env) -> FundService:
    return FundService(env.engine, env.runner)


def set_shop_no(env, value: str) -> None:
    with env.engine.begin() as conn:
        conn.execute(sa.text("UPDATE shop SET shop_no = :no WHERE id = :id"),
                     {"no": value, "id": env.shop_id})


async def test_sync_unsettled_and_margin(env):
    set_shop_no(env, SHOP_NO)
    env.transport.responses[:] = [reply(fx("fund_unsettled")), reply(fx("fund_margin"))]
    svc = service(env)
    (outcome,) = await svc.sync([env.shop_id], "admin")
    assert (outcome.unsettled_count, outcome.margin_synced, outcome.error) == (2, True, None)

    summary = svc.summary([env.shop_id])
    assert summary["total_unsettled_amount_cents"] == 50568
    assert summary["total_unsettled_count"] == 2
    shop = summary["shops"][0]
    assert shop["shop_name"] == "店A"
    assert shop["margin_balance_cents"] == 1000
    assert shop["margin_level"] == "low"

    rows, total = svc.list_unsettled([env.shop_id])
    assert total == 2
    assert rows[0]["display"]["product_name"] in {"测试商品 A", "测试商品 B"}
    assert rows[0]["display"]["settlement_delay_days"] == 21

    margins = svc.list_margin([env.shop_id])
    assert len(margins) == 1
    assert margins[0]["basic_balance_cents"] == 50000

    unsettled_body = env.transport.requests[0]["json"]
    assert unsettled_body["query_type"] == "SHOP_UNSETTLED_ORDER"
    assert unsettled_body["page"] == 0  # 资金 0-based
    assert env.transport.requests[1]["params"]["bizId"] == SHOP_NO


async def test_sync_without_shop_no_skips_margin(env):
    env.transport.responses[:] = [reply(fx("fund_unsettled"))]
    (outcome,) = await service(env).sync([env.shop_id], "admin")
    assert outcome.unsettled_count == 2
    assert outcome.margin_synced is False
    assert outcome.note and "缺少店铺编号" in outcome.note
    # 没有店铺编号就不发保证金请求
    assert len(env.transport.requests) == 1


async def test_bills_upstream_shape_and_amount_status(env):
    env.transport.responses[:] = [reply(fx("fund_bills_item"))]
    (result,) = await service(env).bills([env.shop_id], "admin", days=7)
    assert result.source == "upstream"
    assert result.total == 2
    confirmed, pending = result.items
    assert (confirmed["amount_cents"], confirmed["amount_status"]) == (1234, "confirmed")
    assert confirmed["amount_field"] == "settle_amount"
    assert (pending["amount_cents"], pending["amount_status"]) == (0, "pending")

    body = env.transport.requests[0]["json"]
    assert body["query_type"] == "CHARGE_BILL_ITEM"
    assert body["time_type"] == "BILL_TIME"
    assert isinstance(body["start_time"], str) and isinstance(body["end_time"], str)


async def test_bills_empty_for_new_shop(env):
    env.transport.responses[:] = [reply(fx("fund_bills_empty"))]
    (result,) = await service(env).bills([env.shop_id], "admin")
    assert (result.total, result.items, result.error) == (0, [], None)


async def test_unsettled_paging_incomplete_keeps_old_snapshot(env):
    """分页上限内没拉全时，待结算快照保持旧数据，不能写成半份。"""
    body = fx("fund_unsettled")
    template = json.loads(body["data"][0])
    full_page = {
        **body, "total": 50,
        "data": [json.dumps({**template, "sku_order_no": f"{i}-1"}, ensure_ascii=False)
                 for i in range(50)],
    }
    env.transport.responses[:] = [reply(full_page)]
    svc = FundService(env.engine, env.runner, max_pages=1)
    (outcome,) = await svc.sync([env.shop_id], "admin")
    assert outcome.unsettled_count == 0
    assert outcome.note and "未覆盖旧数据" in outcome.note
    assert svc.list_unsettled([env.shop_id])[1] == 0
