import json

import pytest

from app.adapter.doudian import endpoints as ep
from app.adapter.doudian.client import FxgClient, ShopCredentials
from app.adapter.doudian.errors import (
    BizRejected,
    EgressUnavailable,
    ParseError,
    RiskBlocked,
    SessionExpired,
    TransientError,
)
from app.adapter.doudian.pacer import ShopPacer
from app.adapter.doudian.transport import TransportResponse
from tests.fakes import FakeTransport, ok, reply

TOKEN = "tok_" + "x" * 8
COOKIE_VAL = "ck_" + "y" * 8
UA = "TestAgent/1.0"


def make_creds() -> ShopCredentials:
    return ShopCredentials(
        shop_id=7,
        cookies=[
            {"name": "sessionid", "value": COOKIE_VAL, "domain": ".jinritemai.com", "path": "/"},
            {"name": "other", "value": "o", "domain": "other.example.com", "path": "/"},
            {"name": "narrow", "value": "n", "domain": "fxg.jinritemai.com", "path": "/admin"},
        ],
        token=TOKEN,
        device_headers={"User-Agent": UA, "sec-ch-ua": '"Test";v="1"'},
    )


class Env:
    def __init__(self, responses):
        self.transport = FakeTransport(list(responses))
        self.sleeps: list[float] = []
        self.records = []
        self.pacer_sleeps: list[float] = []

        async def pacer_sleep(s):
            self.pacer_sleeps.append(s)

        async def sleep(s):
            self.sleeps.append(s)

        self.client = FxgClient(
            self.transport, make_creds(), ShopPacer(sleep=pacer_sleep, rand=lambda a, b: a),
            self.records.append, actor="admin", sleep=sleep,
        )


async def test_injects_common_params():
    env = Env([ok()])
    await env.client.call(ep.SEARCHLIST, params={"page": 0})
    req = env.transport.requests[0]
    assert req["method"] == "GET" and req["url"] == "https://fxg.jinritemai.com/api/order/searchlist"
    p = req["params"]
    assert (p["appid"], p["aid"], p["_bid"], p["__token"]) == (1, 4272, "ffa_order", TOKEN)
    assert len(str(p["_lid"])) == 12 and str(p["_lid"]).isdigit()
    assert p["page"] == 0


async def test_cookies_matched_by_domain_and_path():
    env = Env([ok()])
    await env.client.call(ep.TABCNT)
    assert env.transport.requests[0]["cookies"] == {"sessionid": COOKIE_VAL}


async def test_tabcnt_fixed_params():
    env = Env([ok()])
    await env.client.call(ep.TABCNT, params={"tab": "stock_up"})
    p = env.transport.requests[0]["params"]
    assert p["tabcnt_version"] == "v1" and p["tab"] == "all"  # 固定参数不可被覆盖


async def test_express_list_is_post_json_with_common_params_in_body():
    env = Env([ok()])
    await env.client.call(ep.EXPRESS_LIST)
    req = env.transport.requests[0]
    assert req["method"] == "POST" and req["data"] is None
    assert req["json"]["appid"] == 1 and req["json"]["__token"] == TOKEN
    assert "__token" not in (req["params"] or {})


@pytest.mark.parametrize("code", [0, "0", "100000", 100000])
async def test_success_code_variants(code):
    env = Env([ok({"x": 1}, code=code)])
    resp = await env.client.call(ep.TABCNT)
    assert resp["data"] == {"x": 1}


async def test_session_expired():
    env = Env([ok(code=10008)])
    with pytest.raises(SessionExpired):
        await env.client.call(ep.TABCNT)


async def test_risk_blocked():
    env = Env([reply({"code": "10001010A", "msg": "risk"})])
    with pytest.raises(RiskBlocked) as ei:
        await env.client.call(ep.TABCNT)
    assert ei.value.code == "10001010A"


async def test_unknown_code_biz_rejected():
    env = Env([reply({"code": 602500705, "msg": "bad"})])
    with pytest.raises(BizRejected) as ei:
        await env.client.call(ep.SEARCHLIST)
    assert ei.value.code == "602500705" and env.sleeps == []


async def test_read_retries_transient():
    env = Env([TransportResponse(502, b""), TransportResponse(502, b""), ok({"a": 1})])
    resp = await env.client.call(ep.TABCNT)
    assert resp["data"] == {"a": 1}
    assert env.sleeps == [1, 2] and len(env.transport.requests) == 3


async def test_read_gives_up_after_three_retries():
    env = Env([TransportResponse(503, b"")] * 4)
    with pytest.raises(TransientError):
        await env.client.call(ep.TABCNT)
    assert env.sleeps == [1, 2, 4] and len(env.transport.requests) == 4


async def test_429_is_transient():
    env = Env([TransportResponse(429, b""), ok()])
    await env.client.call(ep.TABCNT)
    assert env.sleeps == [1]


async def test_write_endpoint_not_retried():
    write_ep = ep.Endpoint("w", "POST", "/api/x", "ffa_order", "json", write=True)
    env = Env([TransportResponse(502, b"")])
    with pytest.raises(TransientError):
        await env.client.call(write_ep)
    assert env.sleeps == [] and len(env.transport.requests) == 1


async def test_egress_unavailable_not_retried():
    env = Env([EgressUnavailable("proxy down")])
    with pytest.raises(EgressUnavailable):
        await env.client.call(ep.TABCNT)
    assert env.sleeps == [] and len(env.transport.requests) == 1


async def test_bad_body_is_parse_error():
    for body in (b"<html>", b"[]", json.dumps({"msg": "no code"}).encode()):
        env = Env([TransportResponse(200, body)])
        with pytest.raises(ParseError):
            await env.client.call(ep.TABCNT)


async def test_device_headers_used():
    env = Env([ok()])
    await env.client.call(ep.TABCNT)
    h = env.transport.requests[0]["headers"]
    assert h["User-Agent"] == UA and h["sec-ch-ua"] == '"Test";v="1"'


async def test_pacer_called_once_per_call():
    env = Env([TransportResponse(502, b""), ok(), ok()])
    await env.client.call(ep.TABCNT)
    await env.client.call(ep.TABCNT)
    assert env.pacer_sleeps == [0.3, 0.3]


async def test_pacer_range():
    seen = []
    pacer = ShopPacer(sleep=lambda s: _record(seen, s), rand=lambda a, b: (a, b))
    await pacer.wait()
    assert seen == [(0.3, 1.2)]


async def _record(seen, s):
    seen.append(s)


async def test_observer_redacts_and_actor():
    env = Env([ok({"n": 1})])
    await env.client.call(ep.SEARCHLIST, params={"page": 0, "token": TOKEN})
    (rec,) = env.records
    assert rec.actor == "admin" and rec.shop_id == 7 and rec.action == "searchlist"
    assert rec.result == "ok"
    dumped = json.dumps([rec.req_summary, rec.resp_summary], ensure_ascii=False)
    assert TOKEN not in dumped and COOKIE_VAL not in dumped


async def test_observer_records_failures():
    env = Env([ok(code=10008)])
    with pytest.raises(SessionExpired):
        await env.client.call(ep.TABCNT)
    assert env.records[0].result == "SessionExpired"
