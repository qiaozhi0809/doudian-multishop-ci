import json
from pathlib import Path

import pytest

from app.adapter.doudian.errors import BizRejected
from app.service.catalog import CatalogService
from tests.fakes import reply
from tests.service.support import Env

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "m5"


def fx(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.fixture
def env(engine, tmp_path):
    return Env(engine, tmp_path, responses=[])


def service(env) -> CatalogService:
    return CatalogService(env.engine, env.runner)


async def test_product_sync_list_counts_groups(env):
    env.transport.responses[:] = [
        reply(fx("product_list")), reply(fx("product_counts")), reply(fx("product_groups")),
    ]
    svc = service(env)
    (outcome,) = await svc.sync_products([env.shop_id], "admin")
    assert (outcome.fetched, outcome.complete, outcome.error) == (2, True, None)

    rows, total = svc.list_products([env.shop_id])
    assert total == 2
    assert rows[0]["shop_name"] == "店A"
    assert rows[0]["display"]["category_name"] == "测试类目"

    filtered, filtered_total = svc.list_products([env.shop_id], keyword="商品 A")
    assert filtered_total == 1

    (counts,) = await svc.product_counts([env.shop_id], "admin")
    assert counts.source == "upstream" and counts.counts["onsale"] == 6

    (groups,) = await svc.product_groups([env.shop_id], "admin")
    assert groups.source == "upstream"
    assert groups.items == [{"group_id": "1001", "name": "默认分组"},
                            {"group_id": "1002", "name": "清仓"}]

    assert env.transport.requests[0]["params"]["page"] == 0  # 商品列表 0-based


async def test_stock_sync_list_summary_and_warehouses(env):
    env.transport.responses[:] = [
        reply(fx("product_list")), reply(fx("stock_list")), reply(fx("warehouses")),
    ]
    svc = service(env)
    await svc.sync_products([env.shop_id], "admin")
    (outcome,) = await svc.sync_stock([env.shop_id], "admin")
    assert (outcome.fetched, outcome.complete) == (2, True)
    assert (outcome.alarm_count, outcome.sold_out_count) == (1, 1)

    rows, total = svc.list_stock([env.shop_id])
    assert total == 2
    by_id = {r["product_id"]: r for r in rows}
    assert by_id["3811109459833520578"]["name"] == "测试商品 A"
    assert by_id["3811109459833520579"]["is_alarming"] == 1

    alarm_rows, alarm_total = svc.list_stock([env.shop_id], alarm_only=True)
    assert alarm_total == 1 and alarm_rows[0]["product_id"] == "3811109459833520579"
    assert svc.stock_summary([env.shop_id]) == {
        "total": 2, "alarm_count": 1, "sold_out_count": 1,
    }

    (warehouses,) = await svc.warehouses([env.shop_id], "admin")
    assert [w["warehouse_id"] for w in warehouses.items] == ["w1", "w2"]

    assert env.transport.requests[1]["json"]["page"] == 1  # 库存列表 1-based


async def test_failures_are_isolated_per_shop(env):
    env.transport.responses[:] = [BizRejected("100021", "商品数据不可用")]
    (result,) = await service(env).product_counts([env.shop_id], "admin")
    assert result.source == "error"
    assert result.counts is None
    assert result.error and "商品数据不可用" in result.error
