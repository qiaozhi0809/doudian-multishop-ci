import json

import sqlalchemy as sa

from tests.api.conftest import proxy_url
from tests.fakes import ok

TOKEN_A = "tok_" + "a" * 8


def audit_rows(api, like: str = "shop.%"):
    with api.app.state.engine.connect() as conn:
        return [dict(r) for r in conn.execute(sa.text(
            "SELECT shop_id, actor, action, req_summary, resp_summary, result FROM audit_log "
            "WHERE action LIKE :p ORDER BY id"), {"p": like}).mappings()]


def events_of(api, name: str = "shop_status_changed"):
    return [d for e, d in api.events if e == name]


def test_resume_audited_with_actor(api):
    sid = api.new_shop()
    api.login(sid, TOKEN_A)
    api.transport.queue(TOKEN_A, ok(code="602502151"))
    api.client.post(f"/api/shops/{sid}/probe")
    api.events.clear()
    assert api.client.post(f"/api/shops/{sid}/resume").status_code == 200
    (row,) = [r for r in audit_rows(api) if r["action"] == "shop.resume"]
    assert (row["shop_id"], row["actor"], row["result"]) == (sid, "admin", "ok")
    assert json.loads(row["req_summary"]) == {"previous_reason": "risk_blocked:602502151"}
    assert {"shop_id": sid, "status": "active", "paused_reason": None} in events_of(api)


def test_enable_disable_audited_and_pushed(api):
    sid = api.new_shop(ip_n=None)
    api.events.clear()
    api.client.patch(f"/api/shops/{sid}", json={"enabled": False})
    api.client.patch(f"/api/shops/{sid}", json={"enabled": False})  # 重复停用不重复记录
    api.client.patch(f"/api/shops/{sid}", json={"enabled": True})
    api.client.patch(f"/api/shops/{sid}", json={"name": "只改名"})
    assert [(r["action"], r["actor"]) for r in audit_rows(api)] == [
        ("shop.disable", "admin"), ("shop.enable", "admin")]
    assert [e["status"] for e in events_of(api)] == ["disabled", "needs_login"]


def test_set_egress_audit_has_no_credentials(api):
    sid = api.new_shop(ip_n=None)
    api.events.clear()
    url = proxy_url(5)
    api.client.put(f"/api/shops/{sid}/egress", json={"mode": "proxy", "proxy_url": url})
    api.client.put(f"/api/shops/{sid}/egress", json={
        "mode": "proxy", "paste": "203.0.113.6|8000|u6|pw6secret|2026-12-25"})
    rows = audit_rows(api)
    assert [r["action"] for r in rows] == ["shop.set_egress", "shop.set_egress"]
    assert json.loads(rows[0]["req_summary"]) == {
        "mode": "proxy", "proxy_display": "203.0.113.5:8000"}
    dump = json.dumps(rows, ensure_ascii=False)
    for secret in ("pw5secret", "pw6secret", "u5:", "u6:", "http://"):
        assert secret not in dump
    assert all(r["actor"] == "admin" for r in rows)
    assert len(events_of(api)) == 2


def test_accept_egress_change_audited(api):
    sid = api.new_shop()
    api.ips[proxy_url(5)] = "203.0.113.77"  # 出口 IP 变了
    assert api.client.post(f"/api/shops/{sid}/egress/check").json()["egress_status"] == "changed"
    assert audit_rows(api) == [r for r in audit_rows(api) if r["action"] == "shop.set_egress"]
    api.client.post(f"/api/shops/{sid}/egress/check?accept_change=true")
    (row,) = [r for r in audit_rows(api) if r["action"] == "shop.accept_egress_change"]
    assert row["actor"] == "admin" and json.loads(row["resp_summary"]) == {"egress_status": "ok"}
    assert "pw5secret" not in json.dumps(row)
