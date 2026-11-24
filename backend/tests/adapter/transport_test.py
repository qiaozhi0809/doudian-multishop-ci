import pytest

from app.adapter.doudian.errors import EgressUnavailable, TransientError
from app.adapter.doudian.transport import CurlTransport

DEAD = "http://127.0.0.1:1"


async def test_dead_proxy_raises_egress_unavailable_not_direct():
    t = CurlTransport(proxy="http://u:p@127.0.0.1:1", impersonate="chrome")
    with pytest.raises(EgressUnavailable) as ei:
        await t.request("GET", DEAD + "/x", params={}, json=None, data=None, cookies={}, headers={})
    assert "u:p" not in str(ei.value)


async def test_direct_connect_failure_is_transient():
    t = CurlTransport(proxy=None, impersonate="chrome")
    with pytest.raises(TransientError) as ei:
        await t.request("GET", DEAD + "/x", params={}, json=None, data=None, cookies={}, headers={})
    assert not isinstance(ei.value, EgressUnavailable)
