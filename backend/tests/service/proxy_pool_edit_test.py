import asyncio

import pytest

from app.domain.egress_rules import proxy_identity
from app.domain.errors import NotFound
from app.service.egress import ProxyPoolInUse
from app.service.egress_probe import ProbeResult
from app.service.events import EventBus
from app.service.proxy_pool import ProxyPoolService
from app.store import proxy_pool_store, shop_store
from tests.service.proxy_pool_support import (
    PW,
    T0,
    USER,
    audit_text,
    bind,
    box,  # noqa: F401  (夹具)
    good,
    imported_id,
    noop_probe,
    pool,
    probe_returning,
    ready,
    shop,
    svc,  # noqa: F401  (夹具)
)


async def test_change_password_resets_bound_shop(engine, box):
    events = EventBus()
    svc = ProxyPoolService(engine, box, events, noop_probe, clock=lambda: T0)
    sid, pid = bind(engine, box, shop_name="店A")
    ready(engine, sid)
    sub = events.subscribe()
    svc.update(pid, password="new-secret-pw", actor="admin")
    row = shop(engine, sid)
    assert row["status"] == "needs_login" and row["egress_ip"] is None
    assert row["egress_status"] == "unchecked"
    event, data = await anext(sub)
    assert event == "shop_status_changed"
    assert data == {"shop_id": sid, "status": "needs_login", "egress_status": "unchecked"}
    item = pool(engine, pid)
    assert box.decrypt(item["proxy_url"]).decode() == f"http://{USER}:new-secret-pw@203.0.113.5:8000"
    assert item["identity"] == proxy_identity(f"http://{USER}:new-secret-pw@203.0.113.5:8000")
    assert item["proxy_display"] == "203.0.113.5:8000"
    assert "new-secret-pw" not in audit_text(engine)


async def test_change_host_updates_display_and_resets_disabled_shop_egress_only(engine, box):
    events = EventBus()
    svc = ProxyPoolService(engine, box, events, noop_probe, clock=lambda: T0)
    sid, pid = bind(engine, box, shop_name="停用店", status="disabled")
    with engine.begin() as conn:
        shop_store.set_egress(conn, sid, "2026-11-25T00:00:00Z", egress_ip="198.51.100.1")
    sub = events.subscribe()
    svc.update(pid, host="203.0.113.9", port=9000, actor="admin")
    assert pool(engine, pid)["proxy_display"] == "203.0.113.9:9000"
    row = shop(engine, sid)
    assert row["status"] == "disabled" and row["egress_ip"] is None
    assert row["egress_status"] == "unchecked"
    with pytest.raises(asyncio.TimeoutError):  # 状态没变，不发事件
        await asyncio.wait_for(anext(sub), 0.05)


def test_change_expiry_only_leaves_shop_untouched(svc, engine, box):
    sid, pid = bind(engine, box)
    ready(engine, sid)
    before = shop(engine, sid)
    cipher = pool(engine, pid)["proxy_url"]
    svc.update(pid, expires_at="2027-12-31", actor="admin")
    after = shop(engine, sid)
    assert after.pop("proxy_expires_at") == "2027-12-31"  # 经 JOIN 读到新值
    assert after == {k: v for k, v in before.items() if k != "proxy_expires_at"}
    item = pool(engine, pid)
    assert item["expires_at"] == "2027-12-31" and item["proxy_url"] == cipher


def test_clear_expiry_sets_null_and_leaves_shop_untouched(svc, engine, box):
    sid, pid = bind(engine, box)
    ready(engine, sid)
    svc.update(pid, expires_at="2027-12-31", actor="admin")
    before = shop(engine, sid)
    cipher = pool(engine, pid)["proxy_url"]
    svc.update(pid, expires_at=None, actor="admin")
    item = pool(engine, pid)
    assert item["expires_at"] is None and item["proxy_url"] == cipher
    after = shop(engine, sid)
    assert after.pop("proxy_expires_at") is None
    assert after == {k: v for k, v in before.items() if k != "proxy_expires_at"}
    assert "proxy_pool.update" in audit_text(engine)


def test_update_with_nothing_to_change_writes_no_audit(svc, engine, box):
    _, pid = bind(engine, box)
    before = audit_text(engine)
    svc.update(pid, actor="admin")
    svc.update(pid, host="203.0.113.5", password=PW, actor="admin")
    assert audit_text(engine) == before


@pytest.mark.parametrize("host", [
    "x@5.6.7.8", "a/b", "a?b", "a#b", "a:b", "[::1]", "::1", "a b", "a\tb"])
def test_edit_bad_host_rejected_and_nothing_written(svc, engine, box, host):
    sid, pid = bind(engine, box)
    ready(engine, sid)
    before_shop, before_item = shop(engine, sid), pool(engine, pid)
    with pytest.raises(ValueError, match="代理主机格式不正确") as e:
        svc.update(pid, host=host, actor="admin")
    assert PW not in str(e.value) and USER not in str(e.value)
    assert shop(engine, sid) == before_shop and pool(engine, pid) == before_item


def test_same_values_do_not_reset(svc, engine, box):
    sid, pid = bind(engine, box)
    ready(engine, sid)
    before = shop(engine, sid)
    svc.update(pid, host="203.0.113.5", password=PW, actor="admin")
    assert shop(engine, sid) == before


def test_edit_into_existing_identity_conflicts(svc, engine, box):
    svc.import_text(f"{good(1)}\n{good(2)}", "admin")
    with engine.connect() as conn:
        a, b = [r["id"] for r in proxy_pool_store.list_with_usage(conn)]
    before = pool(engine, b)
    with pytest.raises(ProxyPoolInUse) as e:
        svc.update(b, host="203.0.113.1", username=f"{USER}1", actor="admin")
    assert "203.0.113.1:8000" in str(e.value) and PW not in str(e.value)
    assert "店铺" not in str(e.value) and "重复" in str(e.value)
    assert pool(engine, b) == before
    assert a


def test_edit_into_identity_of_item_bound_to_enabled_shop_names_shop(svc, engine, box):
    bind(engine, box, shop_name="占用店")
    svc.import_text(good(2), "admin")
    with engine.connect() as conn:
        other = [r for r in proxy_pool_store.list_with_usage(conn) if r["in_use_shop_id"] is None]
    with pytest.raises(ProxyPoolInUse, match="占用店"):
        svc.update(other[0]["id"], host="203.0.113.5", username=USER, password=PW, actor="admin")


@pytest.mark.parametrize("port", [0, 65536, -1])
def test_edit_invalid_port_rejected_and_nothing_written(svc, engine, box, port):
    sid, pid = bind(engine, box)
    ready(engine, sid)
    before_shop, before_item = shop(engine, sid), pool(engine, pid)
    with pytest.raises(ValueError):
        svc.update(pid, port=port, actor="admin")
    assert shop(engine, sid) == before_shop and pool(engine, pid) == before_item


def test_edit_invalid_expiry_and_empty_host_rejected(svc, engine, box):
    _, pid = bind(engine, box)
    with pytest.raises(ValueError, match="到期日格式应为 YYYY-MM-DD"):
        svc.update(pid, expires_at="2027-13-45", actor="admin")
    with pytest.raises(ValueError):
        svc.update(pid, host="", actor="admin")


def test_edit_missing_item_not_found(svc):
    with pytest.raises(NotFound):
        svc.update(999, password="x", actor="admin")


def test_edit_error_messages_never_contain_password(svc, engine, box):
    svc.import_text(f"{good(1)}\n{good(2)}", "admin")
    with engine.connect() as conn:
        b = proxy_pool_store.list_with_usage(conn)[1]["id"]
    errors = []
    for kw in ({"port": 0}, {"expires_at": "bad"}, {"host": ""},
               {"host": "203.0.113.1", "username": f"{USER}1"}):
        with pytest.raises((ValueError, ProxyPoolInUse)) as e:
            svc.update(b, actor="admin", **kw)
        errors.append(str(e.value))
    assert not any(PW in m or USER in m for m in errors)



async def test_check_success_records_ip(engine, box):
    probe = probe_returning(ProbeResult("198.51.100.7", None))
    svc = ProxyPoolService(engine, box, EventBus(), probe, clock=lambda: T0)
    pid = imported_id(svc, engine)
    sid, bound = bind(engine, box, url="http://u:p@203.0.113.50:8000")
    before = shop(engine, sid)
    r = await svc.check(pid, "admin")
    assert (r.ip, r.reason, r.ip_in_use_by) == ("198.51.100.7", None, None)
    assert r.elapsed_ms >= 0
    assert probe.seen == f"http://{USER}1:{PW}@203.0.113.1:8000"
    item = pool(engine, pid)
    assert item["last_check_ip"] == "198.51.100.7"
    assert item["last_checked_at"] == "2026-12-01T00:00:00Z"
    assert shop(engine, sid) == before and bound


async def test_check_failure_clears_ip_and_returns_reason(engine, box):
    ok = ProxyPoolService(
        engine, box, EventBus(), probe_returning(ProbeResult("198.51.100.7", None)),
        clock=lambda: T0)
    pid = imported_id(ok, engine)
    await ok.check(pid, "admin")
    bad = ProxyPoolService(
        engine, box, EventBus(), probe_returning(ProbeResult(None, "timeout")),
        clock=lambda: T0)
    r = await bad.check(pid, "admin")
    assert (r.ip, r.reason, r.ip_in_use_by) == (None, "timeout", None)
    item = pool(engine, pid)
    assert item["last_check_ip"] is None and item["last_checked_at"] == "2026-12-01T00:00:00Z"


async def test_check_reports_ip_used_by_other_shop(engine, box):
    svc = ProxyPoolService(
        engine, box, EventBus(), probe_returning(ProbeResult("198.51.100.1", None)),
        clock=lambda: T0)
    pid = imported_id(svc, engine)
    sid, _ = bind(engine, box, shop_name="店B", url="http://u:p@203.0.113.50:8000")
    ready(engine, sid, ip="198.51.100.1")
    r = await svc.check(pid, "admin")
    assert r.ip_in_use_by == {"shop_id": sid, "shop_name": "店B"}


async def test_check_ignores_disabled_shop_with_same_ip(engine, box):
    svc = ProxyPoolService(
        engine, box, EventBus(), probe_returning(ProbeResult("198.51.100.1", None)),
        clock=lambda: T0)
    pid = imported_id(svc, engine)
    sid, _ = bind(engine, box, url="http://u:p@203.0.113.50:8000")
    ready(engine, sid, ip="198.51.100.1")
    with engine.begin() as conn:
        shop_store.set_status(conn, sid, "disabled", "2026-11-25T00:00:00Z")
    assert (await svc.check(pid, "admin")).ip_in_use_by is None


async def test_check_ignores_own_bound_shop(engine, box):
    probe = probe_returning(ProbeResult("198.51.100.1", None))
    svc = ProxyPoolService(engine, box, EventBus(), probe, clock=lambda: T0)
    sid, pid = bind(engine, box)
    ready(engine, sid, ip="198.51.100.1")
    r = await svc.check(pid, "admin")
    assert r.ip == "198.51.100.1" and r.ip_in_use_by is None


async def test_check_missing_item_not_found(svc):
    with pytest.raises(NotFound):
        await svc.check(999, "admin")

