"""代理池服务测试的共享夹具与辅助函数（proxy_pool_test / proxy_pool_edit_test 共用）。"""

from datetime import UTC, datetime

import pytest
import sqlalchemy as sa

from app.service.egress import EgressService
from app.service.egress_probe import ProbeResult
from app.service.events import EventBus
from app.service.proxy_pool import ProxyPoolService
from app.shared.secret_box import DevKeyBox
from app.store import proxy_pool_store, shop_store
from app.store.schema import audit_log

T0 = datetime(2026, 12, 1, 0, 0, 0, tzinfo=UTC)
PW = "pw-not-in-ciphertext"
USER = "user-not-in-ciphertext"
URL_A = f"http://{USER}:{PW}@203.0.113.5:8000"


def good(i: int, expires: str = "2027-06-30") -> str:
    return f"203.0.113.{i}|8000|{USER}{i}|{PW}|{expires}"


async def noop_probe(proxy):
    return ProbeResult(None, "network")


@pytest.fixture
def box(tmp_path):
    return DevKeyBox(tmp_path / "k")


@pytest.fixture
def svc(engine, box):
    return ProxyPoolService(engine, box, EventBus(), noop_probe, clock=lambda: T0)


def audit_text(engine) -> str:
    with engine.connect() as conn:
        rows = conn.execute(sa.select(audit_log)).mappings().all()
    return repr([dict(r) for r in rows])


def count(engine) -> int:
    with engine.connect() as conn:
        return len(proxy_pool_store.list_with_usage(conn))


def bind(engine, box, shop_name="店", status=None, url=URL_A) -> tuple[int, int]:
    """建店铺并通过 EgressService 绑定代理，返回 (shop_id, pool_id)。"""
    with engine.begin() as conn:
        sid = shop_store.create(conn, shop_name, "2026-11-25T00:00:00Z")
        if status:
            shop_store.set_status(conn, sid, status, "2026-11-25T00:00:00Z")
    egress = EgressService(engine, box, EventBus(), fake_fetch, clock=lambda: T0)
    egress.set_egress(sid, "proxy", proxy_url=url)
    with engine.connect() as conn:
        return sid, shop_store.get(conn, sid)["proxy_pool_id"]


async def fake_fetch(proxy):
    return None



def ready(engine, shop_id: int, ip="198.51.100.1") -> None:
    """把店铺置为已登录、出口已确认。"""
    with engine.begin() as conn:
        shop_store.set_status(conn, shop_id, "active", "2026-11-25T00:00:00Z")
        shop_store.set_egress(
            conn, shop_id, "2026-11-25T00:00:00Z", egress_ip=ip, egress_status="ok",
            egress_checked_at="2026-11-25T00:00:00Z")


def shop(engine, sid):
    with engine.connect() as conn:
        return dict(shop_store.get(conn, sid))


def pool(engine, pid):
    with engine.connect() as conn:
        return dict(proxy_pool_store.get(conn, pid))



def probe_returning(result):
    async def probe(proxy):
        probe.seen = proxy
        return result
    return probe


def imported_id(svc, engine) -> int:
    svc.import_text(good(1), "admin")
    with engine.connect() as conn:
        return proxy_pool_store.list_with_usage(conn)[0]["id"]

