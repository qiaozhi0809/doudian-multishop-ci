import hashlib
from datetime import timedelta

import sqlalchemy as sa

from tests.conftest import ADMIN_PASSWORD, ADMIN_USER

CREDS = {"username": ADMIN_USER, "password": ADMIN_PASSWORD}
WRONG = {"username": ADMIN_USER, "password": "wrong_" + "y" * 6}


def setup(client):
    return client.post("/api/auth/setup", json=CREDS)


def rows(app, sql):
    with app.state.engine.connect() as conn:
        return conn.execute(sa.text(sql)).all()


def test_status_flow(client):
    assert client.get("/api/auth/status").json() == {
        "initialized": False, "authenticated": False, "username": None}
    setup(client)
    assert client.get("/api/auth/status").json()["initialized"] is True
    client.post("/api/auth/login", json=CREDS)
    assert client.get("/api/auth/status").json() == {
        "initialized": True, "authenticated": True, "username": ADMIN_USER}


def test_setup_only_once(client):
    assert setup(client).status_code == 201
    r = client.post("/api/auth/setup", json={"username": "other", "password": "another_pw_1"})
    assert r.status_code == 409 and r.json()["error"]["type"] == "AlreadyInitialized"


def test_setup_rejects_short_password(client):
    r = client.post("/api/auth/setup", json={"username": "a", "password": "short"})
    assert r.status_code == 422
    assert r.json()["error"]["detail"]["problems"] == ["密码至少 8 位"]
    assert client.get("/api/auth/status").json()["initialized"] is False


def test_protected_requires_login(app, client):
    app.add_api_route("/api/_probe", lambda: {"ok": True})
    r = client.get("/api/_probe")
    assert r.status_code == 401
    assert set(r.json()["error"]) == {"type", "message", "shop_id", "detail"}
    setup(client)
    client.post("/api/auth/login", json=CREDS)
    assert client.get("/api/_probe").json() == {"ok": True}
    assert client.get("/api/health").status_code == 200  # 公开接口


def test_public_endpoints_open_without_login(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/auth/status").status_code == 200
    assert client.post("/api/auth/password", json={
        "old_password": "a", "new_password": "b" * 8}).status_code == 401


def test_login_failure_message_uniform(client):
    setup(client)
    unknown = client.post("/api/auth/login", json={"username": "nobody", "password": "x" * 8})
    wrong = client.post("/api/auth/login", json=WRONG)
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


def test_locked_returns_423(client):
    setup(client)
    for _ in range(5):
        assert client.post("/api/auth/login", json=WRONG).status_code == 401
    locked = client.post("/api/auth/login", json=CREDS)  # 密码正确也不行
    assert locked.status_code == 423 and locked.json()["error"]["type"] == "AccountLocked"


def test_lock_and_relock(client, clock):
    setup(client)
    for _ in range(5):
        client.post("/api/auth/login", json=WRONG)
    assert client.post("/api/auth/login", json=CREDS).status_code == 423
    clock.now += timedelta(minutes=5, seconds=1)  # 锁定到期
    for i in range(5):
        assert client.post("/api/auth/login", json=WRONG).status_code == 401, i
    assert client.post("/api/auth/login", json=CREDS).status_code == 423  # 再次锁定


def test_success_resets_failure_count(client):
    setup(client)
    for _ in range(4):
        client.post("/api/auth/login", json=WRONG)
    assert client.post("/api/auth/login", json=CREDS).status_code == 200
    for _ in range(4):
        client.post("/api/auth/login", json=WRONG)
    assert client.post("/api/auth/login", json=CREDS).status_code == 200  # 没有累计到 5


def test_cookie_flags(client):
    setup(client)
    header = client.post("/api/auth/login", json=CREDS).headers["set-cookie"].lower()
    assert header.startswith("dd_admin=")
    for part in ("httponly", "samesite=strict", "path=/", "max-age=604800"):
        assert part in header


def test_token_not_stored_plain(app, client):
    setup(client)
    client.post("/api/auth/login", json=CREDS)
    token = client.cookies.get("dd_admin")
    (stored,) = rows(app, "SELECT token_hash FROM admin_session")
    assert stored[0] == hashlib.sha256(token.encode()).hexdigest() != token
    (user,) = rows(app, "SELECT password_hash FROM admin_user")
    assert user[0].startswith("$argon2id$") and ADMIN_PASSWORD not in user[0]


def test_logout_invalidates_session(client):
    setup(client)
    client.post("/api/auth/login", json=CREDS)
    assert client.post("/api/auth/logout").status_code == 200
    assert client.post("/api/auth/password", json={
        "old_password": ADMIN_PASSWORD, "new_password": "n" * 8}).status_code == 401


def test_session_idle_and_absolute_expiry(app, client, clock):
    app.add_api_route("/api/_probe", lambda: {"ok": True})
    setup(client)
    client.post("/api/auth/login", json=CREDS)
    clock.now += timedelta(hours=11)
    assert client.get("/api/_probe").status_code == 200  # 刷新最近活动时间
    clock.now += timedelta(hours=11)
    assert client.get("/api/_probe").status_code == 200
    clock.now += timedelta(hours=13)  # 空闲超过 12 小时
    assert client.get("/api/_probe").status_code == 401

    client.post("/api/auth/login", json=CREDS)
    for _ in range(16):  # 每 11 小时用一次，累计 176 小时，超过 7 天
        clock.now += timedelta(hours=11)
        last = client.get("/api/_probe").status_code
    assert last == 401  # 自登录起超过 7 天


def test_change_password_revokes_other_sessions(app, client):
    app.add_api_route("/api/_probe", lambda: {"ok": True})
    setup(client)
    client.post("/api/auth/login", json=CREDS)
    first = client.cookies.get("dd_admin")
    client.cookies.clear()
    client.post("/api/auth/login", json=CREDS)
    second = client.cookies.get("dd_admin")
    assert first != second
    new_pw = "new_" + "z" * 8
    r = client.post("/api/auth/password", json={
        "old_password": ADMIN_PASSWORD, "new_password": new_pw})
    assert r.status_code == 200
    assert client.get("/api/_probe").status_code == 200  # 当前会话保留
    client.cookies.clear()
    client.cookies.set("dd_admin", first)
    assert client.get("/api/_probe").status_code == 401  # 其他会话失效
    assert client.post("/api/auth/login", json=CREDS).status_code == 401
    assert client.post("/api/auth/login", json={
        "username": ADMIN_USER, "password": new_pw}).status_code == 200


def test_change_password_wrong_old_or_short_new(client):
    setup(client)
    client.post("/api/auth/login", json=CREDS)
    r = client.post("/api/auth/password", json={
        "old_password": "nope" * 3, "new_password": "n" * 8})
    assert r.status_code == 401
    r = client.post("/api/auth/password", json={
        "old_password": ADMIN_PASSWORD, "new_password": "short"})
    assert r.status_code == 422


def test_rejects_foreign_host(client):
    r = client.get("/api/health", headers={"Host": "evil.example.com"})
    assert r.status_code == 421 and r.json()["error"]["type"] == "HostNotAllowed"
    assert client.get("/api/health", headers={"Host": "localhost:8787"}).status_code == 200
    assert client.get("/api/health", headers={"Host": "localhost:5173"}).status_code == 421


def test_dev_mode_allows_vite_host(tmp_path):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    app = create_app(Settings(data_dir=tmp_path / "d", dev_mode=True))
    with TestClient(app, base_url="http://127.0.0.1:8787") as c:
        assert c.get("/api/health", headers={"Host": "localhost:5173"}).status_code == 200


def test_audit_records_login(app, client):
    setup(client)
    client.post("/api/auth/login", json=WRONG)
    client.post("/api/auth/login", json={"username": "nobody", "password": "zzz_" + "z" * 6})
    client.post("/api/auth/login", json=CREDS)
    client.post("/api/auth/logout")
    got = [tuple(r) for r in rows(app, "SELECT action, actor, result FROM audit_log ORDER BY id")]
    assert got == [
        ("auth.login_failed", "admin", "failed"),
        ("auth.login_failed", "unknown", "failed"),
        ("auth.login_ok", "admin", "ok"),
        ("auth.logout", "admin", "ok"),
    ]
    dump = str(rows(app, "SELECT * FROM audit_log"))
    assert ADMIN_PASSWORD not in dump and "wrong_" not in dump and "nobody" not in dump


def test_validation_error_uses_envelope(client):
    r = client.post("/api/auth/login", json={"username": "a"})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["type"] == "ValidationError" and err["detail"]


def test_logged_in_client_fixture(logged_in_client):
    assert logged_in_client.get("/api/auth/status").json()["authenticated"] is True
