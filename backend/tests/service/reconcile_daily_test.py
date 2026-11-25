"""M7：每日定时对账（overview 13 / backend 5.7）与每日定点调度。"""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.adapter.doudian.transport import TransportResponse
from app.service.periodic import run_daily_at, seconds_until_daily
from app.store import shop_store
from tests.service.m4_support import M4Env

M4 = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "m4"


def searchlist() -> TransportResponse:
    data = json.loads((M4 / "searchlist_all.json").read_bytes())["data"]
    return TransportResponse(200, json.dumps({"code": 0, "msg": "", "data": data}).encode())


@pytest.fixture
def env(engine, tmp_path, clock):
    return M4Env(engine, tmp_path, clock, [])


# ---- 定点调度纯函数 ----

def test_seconds_until_daily():
    now = datetime(2026, 11, 25, 2, 0, tzinfo=UTC)
    assert seconds_until_daily(3, now) == 3600
    assert seconds_until_daily(1, now) == 23 * 3600
    at_hour = datetime(2026, 11, 25, 3, 0, tzinfo=UTC)
    assert seconds_until_daily(3, at_hour) == 24 * 3600  # 正好整点算明天


async def test_run_daily_at_fires_and_stops():
    calls: list[int] = []
    stop = asyncio.Event()

    async def fn() -> None:
        calls.append(1)
        stop.set()

    # now 落在 02:59:59.999 → 距 03:00 只剩 1ms
    now = lambda: datetime(2026, 11, 25, 2, 59, 59, 999_000, tzinfo=UTC)  # noqa: E731
    await asyncio.wait_for(run_daily_at(3, fn, stop, now=now), timeout=1)
    assert calls == [1]


# ---- 全店对账 ----

async def test_run_daily_runs_all_active_shops_and_waits(env):
    env.transport.responses.append(searchlist())

    result = await env.reconcile.run_daily()

    assert result["status"] == "success"
    assert result["scanned"] >= 1
    assert result["shop_ids"] == [env.shop_id]
    latest = env.reconcile.latest_run()
    assert latest["status"] == "success"  # 同步等待完成，不是 running


async def test_run_daily_skips_when_no_active_shops(env):
    with env.engine.begin() as conn:
        shop_store.set_status(conn, env.shop_id, "needs_login", "2026-11-25T00:00:00Z")

    result = await env.reconcile.run_daily()

    assert result == {"run_id": None, "status": "skipped", "reason": "没有可对账的店铺"}
    assert env.transport.requests == []  # 没有可对账店铺时一条请求都不发
