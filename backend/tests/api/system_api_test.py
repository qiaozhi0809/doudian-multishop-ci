"""系统信息 API：演练模式标识与版本号（前端顶部横幅用）。"""

from app.shared.version import APP_VERSION


def test_system_info_defaults(api):
    body = api.client.get("/api/system/info").json()
    assert body["dry_run"] is False
    assert body["version"] == APP_VERSION
    assert body["reconcile_daily"] is True and body["backup_daily"] is True
    assert body["backup_keep"] == 7
    assert body["ship_deadline_warn_hours"] == 6


def test_system_info_reflects_dry_run(api):
    api.app.state.settings.dry_run = True
    assert api.client.get("/api/system/info").json()["dry_run"] is True


def test_system_info_requires_admin(api):
    api.client.cookies.clear()
    assert api.client.get("/api/system/info").status_code == 401
