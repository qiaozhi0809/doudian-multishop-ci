from fastapi.testclient import TestClient

PW = "pw-api-secret"
USER = "user-api-secret"


def line(i: int, expires: str = "2027-06-30") -> str:
    return f"203.0.113.{i}|8000|{USER}{i}|{PW}|{expires}"


def import_one(api, i: int = 5) -> int:
    r = api.client.post("/api/proxy-pool/import", json={"text": line(i)})
    assert r.status_code == 200 and r.json()["added"] == 1
    return api.client.get("/api/proxy-pool").json()[-1]["id"]


def test_requires_login(api):
    with TestClient(api.app, base_url="http://127.0.0.1:8787") as anon:
        assert anon.get("/api/proxy-pool").status_code == 401
        assert anon.post("/api/proxy-pool/import", json={"text": ""}).status_code == 401


def test_import_list_and_no_secrets(api):
    text = "\n".join([line(5), line(6), "bad|line", line(5)])
    r = api.client.post("/api/proxy-pool/import", json={"text": text})
    assert r.status_code == 200
    body = r.json()
    assert (body["added"], body["skipped"], body["failed"]) == (2, 1, 1)
    assert [f["line"] for f in body["failures"]] == [3]
    listed = api.client.get("/api/proxy-pool")
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 2
    assert set(rows[0]) == {
        "id", "proxy_display", "expires_at", "expiry_state", "in_use_by",
        "last_checked_at", "last_check_ip"}
    assert rows[0]["proxy_display"] == "203.0.113.5:8000" and rows[0]["in_use_by"] is None
    assert PW not in r.text + listed.text and USER not in r.text + listed.text


def test_import_over_limit_is_422(api):
    text = "\n".join(line(5) for _ in range(501))
    assert api.client.post("/api/proxy-pool/import", json={"text": text}).status_code == 422


def test_patch_and_validation(api):
    pid = import_one(api)
    r = api.client.patch(f"/api/proxy-pool/{pid}", json={"expires_at": "2028-01-01"})
    assert r.status_code == 200 and r.json()["expires_at"] == "2028-01-01"
    assert api.client.patch(f"/api/proxy-pool/{pid}", json={"port": 70000}).status_code == 422
    assert api.client.patch(
        f"/api/proxy-pool/{pid}", json={"expires_at": "bad"}).status_code == 422
    assert api.client.patch("/api/proxy-pool/999", json={"port": 80}).status_code == 404


def test_delete_free_missing_and_in_use(api):
    pid = import_one(api)
    shop = api.client.post("/api/shops", json={"name": "店A"}).json()["id"]
    assert api.client.put(
        f"/api/shops/{shop}/egress", json={"mode": "proxy", "pool_id": pid}).status_code == 200
    row = api.client.get("/api/proxy-pool").json()[0]
    assert row["in_use_by"] == {"shop_id": shop, "shop_name": "店A"}
    r = api.client.delete(f"/api/proxy-pool/{pid}")
    assert r.status_code == 409 and r.json()["error"]["type"] == "ProxyPoolInUse"
    assert PW not in r.text
    free = import_one(api, 6)
    r = api.client.delete(f"/api/proxy-pool/{free}")
    assert r.status_code == 204 and r.content == b""
    assert api.client.delete(f"/api/proxy-pool/{free}").status_code == 404


def test_check_success_failure_and_missing(api):
    pid = import_one(api)
    api.ips["http://" + f"{USER}5:{PW}@203.0.113.5:8000"] = "203.0.113.5"
    r = api.client.post(f"/api/proxy-pool/{pid}/check")
    assert r.status_code == 200
    assert r.json()["ip"] == "203.0.113.5" and r.json()["reason"] is None
    assert r.json()["ip_in_use_by"] is None and r.json()["elapsed_ms"] >= 0
    assert api.client.get("/api/proxy-pool").json()[0]["last_check_ip"] == "203.0.113.5"
    api.ips.clear()
    r = api.client.post(f"/api/proxy-pool/{pid}/check")
    assert r.json()["ip"] is None and r.json()["reason"] == "network"
    assert PW not in r.text
    assert api.client.post("/api/proxy-pool/999/check").status_code == 404
