"""ENG-06：备份 API（手动触发 + 快照列表）。"""


def test_manual_backup_creates_snapshot(api):
    resp = api.client.post("/api/backup/run")
    assert resp.status_code == 201
    created = resp.json()
    assert created["trigger"] == "manual" and created["size_bytes"] > 0
    assert created["file_name"].startswith("app-") and created["file_name"].endswith(".db")

    listing = api.client.get("/api/backup/snapshots").json()
    assert listing["keep"] == 7
    assert listing["items"][0]["file_name"] == created["file_name"]
    assert listing["items"][0]["exists"] is True
    assert listing["items"][0]["actor"] == "admin"


def test_backup_requires_admin(api):
    api.client.cookies.clear()
    assert api.client.post("/api/backup/run").status_code == 401
    assert api.client.get("/api/backup/snapshots").status_code == 401
