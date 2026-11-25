"""按需解密收件人：限速、缓存、额度冷却（DEC-06、flows 7.3）。"""

from datetime import timedelta
from pathlib import Path

import pytest

from app.adapter.doudian.errors import BizRejected, RiskBlocked
from app.adapter.doudian.transport import TransportResponse
from app.domain.errors import DecryptCooldown, InvalidRequest
from app.service.receiver import ReceiverService
from app.store import shop_store
from tests.fakes import reply
from tests.service.label_support import LabelExecEnv

WRITE = Path(__file__).resolve().parents[1] / "fixtures" / "doudian" / "write"


def fx(name: str) -> TransportResponse:
    return TransportResponse(200, (WRITE / f"{name}.json").read_bytes())


class RecvEnv(LabelExecEnv):
    def __init__(self, engine, tmp_path, clock, responses):
        super().__init__(engine, tmp_path, clock, responses)
        self.sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            self.sleeps.append(seconds)

        self.receiver = ReceiverService(engine, self.runner, clock=clock, sleep=fake_sleep)


async def test_decrypt_returns_and_caches(engine, tmp_path, clock):
    env = RecvEnv(engine, tmp_path, clock, [fx("receiveinfo")])
    oid = env.add_order("6900000000000000001")

    first = await env.receiver.decrypt(oid, "admin")
    second = await env.receiver.decrypt(oid, "admin")

    assert first.name == "张*" and first.phone == "138****0000"
    assert first.region == "内蒙古自治区通辽市科尔沁左翼后旗甘旗卡镇"
    assert first.cached is False
    assert second.cached is True
    assert len(env.transport.requests) == 1
    assert env.transport.requests[0]["url"].endswith("/api/order/receiveinfo")
    assert env.transport.requests[0]["params"]["order_id"] == "6900000000000000001"


async def test_rate_limit_waits_between_orders(engine, tmp_path, clock):
    env = RecvEnv(engine, tmp_path, clock, [fx("receiveinfo"), fx("receiveinfo")])
    oid1 = env.add_order("6900000000000000001")
    oid2 = env.add_order("6900000000000000002")

    await env.receiver.decrypt(oid1, "admin")
    await env.receiver.decrypt(oid2, "admin")

    assert env.sleeps and 1.5 <= env.sleeps[-1] <= 2.0


async def test_decrypt_cache_expires(engine, tmp_path, clock):
    env = RecvEnv(engine, tmp_path, clock, [fx("receiveinfo"), fx("receiveinfo")])
    oid = env.add_order("6900000000000000001")
    await env.receiver.decrypt(oid, "admin")
    clock.now = clock.now + timedelta(days=20)  # 超过平台 expire_time（2026-12-11）
    again = await env.receiver.decrypt(oid, "admin")
    assert again.cached is False
    assert len(env.transport.requests) == 2


async def test_602502151_cools_down_without_pausing_shop(engine, tmp_path, clock):
    env = RecvEnv(engine, tmp_path, clock, [
        reply({"code": "602502151", "msg": "您的账户存在安全风险，请稍后再试"}),
    ])
    oid = env.add_order("6900000000000000001")

    with pytest.raises(DecryptCooldown) as exc:
        await env.receiver.decrypt(oid, "admin")
    assert exc.value.shop_id == env.shop_id
    with engine.connect() as conn:
        assert shop_store.get(conn, env.shop_id)["paused_reason"] is None  # 不暂停整店

    # 冷却期内不再发请求
    with pytest.raises(DecryptCooldown):
        await env.receiver.decrypt(oid, "admin")
    assert len(env.transport.requests) == 1


async def test_other_risk_code_pauses_shop(engine, tmp_path, clock):
    env = RecvEnv(engine, tmp_path, clock, [
        reply({"code": "10001010A", "msg": "当前环境存在风险"}),
    ])
    oid = env.add_order("6900000000000000001")

    with pytest.raises(RiskBlocked):
        await env.receiver.decrypt(oid, "admin")
    with engine.connect() as conn:
        assert shop_store.get(conn, env.shop_id)["paused_reason"] == "risk_blocked:10001010A"


async def test_shipped_order_never_decrypted(engine, tmp_path, clock):
    env = RecvEnv(engine, tmp_path, clock, [])
    oid = env.add_order("6900000000000000001", status="shipped", platform_status=3)
    with pytest.raises(InvalidRequest):
        await env.receiver.decrypt(oid, "admin")
    assert env.transport.requests == []


async def test_verify_type_rejected(engine, tmp_path, clock):
    env = RecvEnv(engine, tmp_path, clock, [fx("receiveinfo")])
    oid = env.add_order("6900000000000000001")
    resp = fx("receiveinfo")
    body = resp.body.replace(b'"verify_type": ""', b'"verify_type": "slide"')
    env.transport.responses = [TransportResponse(200, body)]

    with pytest.raises(BizRejected):
        await env.receiver.decrypt(oid, "admin")
