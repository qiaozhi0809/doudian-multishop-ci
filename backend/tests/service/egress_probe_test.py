import pytest

from app.adapter.doudian.errors import EgressUnavailable, TransientError
from app.adapter.doudian.transport import TransportResponse
from app.service.egress_probe import ProbeResult, make_fetch_ip, make_probe
from tests.fakes import FakeTransport

PROXY = "http://u1:p1@203.0.113.5:8000"


def _factory(transport, seen):
    def make(proxy):
        seen.append(proxy)
        return transport
    return make


async def test_fetch_ip_returns_ip_through_given_proxy():
    seen: list = []
    transport = FakeTransport([TransportResponse(200, b"203.0.113.5\n")])
    fetch = make_fetch_ip("https://echo.example/ip", transport_factory=_factory(transport, seen))
    assert await fetch(PROXY) == "203.0.113.5"
    assert seen == [PROXY]
    assert transport.requests[0]["url"] == "https://echo.example/ip"


async def test_fetch_ip_direct_passes_none():
    seen: list = []
    transport = FakeTransport([TransportResponse(200, b"203.0.113.9")])
    fetch = make_fetch_ip("https://echo.example/ip", transport_factory=_factory(transport, seen))
    assert await fetch(None) == "203.0.113.9"
    assert seen == [None]


async def test_fetch_ip_failures_return_none():
    cases = [
        TransportResponse(200, b"<html>blocked</html>"),
        TransportResponse(500, b"203.0.113.5"),
        EgressUnavailable("down"),
    ]
    for case in cases:
        fetch = make_fetch_ip(
            "https://echo.example/ip", transport_factory=_factory(FakeTransport([case]), [])
        )
        assert await fetch(PROXY) is None


@pytest.mark.parametrize("outcome,reason", [
    (TimeoutError(), "timeout"),
    (EgressUnavailable("x"), "proxy_unavailable"),
    (TransientError("x"), "network"),
    (TransportResponse(500, b"203.0.113.5"), "bad_echo"),
    (TransportResponse(200, b"<html>"), "bad_echo"),
])
async def test_probe_reasons(outcome, reason):
    probe = make_probe(
        "https://echo.example/ip", transport_factory=_factory(FakeTransport([outcome]), [])
    )
    assert await probe(PROXY) == ProbeResult(None, reason)


async def test_probe_success():
    probe = make_probe(
        "https://echo.example/ip",
        transport_factory=_factory(FakeTransport([TransportResponse(200, b"203.0.113.5\n")]), []),
    )
    assert await probe(PROXY) == ProbeResult("203.0.113.5", None)
