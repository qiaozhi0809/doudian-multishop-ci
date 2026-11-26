"""同步收款信息接口：出口未就绪时返回 409，不打开浏览器；浏览器失败返回 422。"""

from app.service import shop_profile as shop_profile_mod


def _fake_scrape(monkeypatch, result=None, error=None):
    calls: list = []

    async def fake(profile_dir, proxy, registry=None):
        calls.append(proxy)
        if error:
            raise error
        return result or {}

    monkeypatch.setattr(shop_profile_mod, "scrape_platform_info", fake)
    return calls


def test_scrape_without_egress_is_rejected_before_browser(api, monkeypatch):
    calls = _fake_scrape(monkeypatch)
    sid = api.new_shop(ip_n=None)
    r = api.client.post(f"/api/shops/{sid}/profile/scrape")
    assert r.status_code == 409
    assert r.json()["error"]["type"] == "EgressNotReady"
    assert calls == []


def test_scrape_browser_failure_is_422(api, monkeypatch):
    _fake_scrape(monkeypatch, error=RuntimeError("page crashed"))
    sid = api.new_shop()
    api.login(sid, "tok-scrape")
    r = api.client.post(f"/api/shops/{sid}/profile/scrape")
    assert r.status_code == 422
    assert "读取平台信息失败" in r.json()["error"]["message"]


def test_patch_null_clears_profile_fields_and_entity(api):
    sid = api.new_shop()
    filled = {"entity": "某主体", "platform_shop_id": "100000001",
              "bank_name": "某某银行", "bank_tail": "0001"}
    assert api.client.patch(f"/api/shops/{sid}", json=filled).status_code == 200
    r = api.client.patch(f"/api/shops/{sid}", json={k: None for k in filled})
    assert r.status_code == 200
    row = r.json()
    assert all(row[k] is None for k in filled), row


def test_patch_omitted_fields_stay(api):
    sid = api.new_shop()
    api.client.patch(f"/api/shops/{sid}", json={"bank_tail": "0001", "entity": "某主体"})
    row = api.client.patch(f"/api/shops/{sid}", json={"name": "改名"}).json()
    assert (row["bank_tail"], row["entity"], row["name"]) == ("0001", "某主体", "改名")


def test_patch_rejects_full_card_number_and_bad_shop_id(api):
    sid = api.new_shop()
    for body, message in (
        ({"bank_tail": "6222000000001234"}, "卡号尾号是 4 位数字"),
        ({"bank_tail": "12a4"}, "卡号尾号是 4 位数字"),
        ({"bank_tail": "１２３４"}, "卡号尾号是 4 位数字"),
        ({"platform_shop_id": "店铺100"}, "店铺ID是 1 到 20 位数字"),
        ({"platform_shop_id": "1" * 21}, "店铺ID是 1 到 20 位数字"),
        ({"bank_name": "示" * 51}, "开户行不超过 50 个字"),
    ):
        r = api.client.patch(f"/api/shops/{sid}", json=body)
        assert r.status_code == 422, body
        assert r.json()["error"]["message"] == message, body
    assert api.shop(sid)["bank_tail"] is None


def test_create_shop_with_platform_shop_id(api):
    r = api.client.post("/api/shops", json={"name": "店E", "platform_shop_id": "100000001"})
    assert r.status_code == 201
    assert r.json()["platform_shop_id"] == "100000001"
    bad = api.client.post("/api/shops", json={"name": "店F", "platform_shop_id": "abc"})
    assert bad.status_code == 422
    assert bad.json()["error"]["message"] == "店铺ID是 1 到 20 位数字"
    assert "店F" not in [s["name"] for s in api.client.get("/api/shops").json()]


def test_scrape_cloak_unavailable_message_is_shown(api, monkeypatch):
    from app.adapter.browser.cloak_launch import BINARY_MISSING, CloakUnavailable

    _fake_scrape(monkeypatch, error=CloakUnavailable(BINARY_MISSING))
    sid = api.new_shop()
    api.login(sid, "tok-scrape")
    r = api.client.post(f"/api/shops/{sid}/profile/scrape")
    assert r.status_code == 422
    assert r.json()["error"]["message"] == BINARY_MISSING
