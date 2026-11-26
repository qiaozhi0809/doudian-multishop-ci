"""手动「同步收款信息」：必须经 ShopRunner（出口、暂停、会话、串行），主体写进 shop.entity。"""

import pytest

from app.service import shop_profile as shop_profile_mod
from app.service.shop_profile import ShopProfileService
from app.service.shop_runner import ShopPaused
from app.store import shop_profile_store, shop_store

NOW = "2026-11-26T00:00:00Z"
SCRAPED = {
    "bank_name": "某某银行", "bank_tail": "0001",
    "platform_shop_id": "100000009", "entity": "某某贸易有限公司",
}


class FakeRunner:
    """记录 run 是否被调用；precheck 不通时直接抛出，模拟出口 / 暂停 / 会话拦截。"""

    def __init__(self, block: Exception | None = None, proxy: str | None = "http://p:1") -> None:
        self.block = block
        self.proxy = proxy
        self.runs: list[int] = []

    async def run(self, shop_id, job, *, actor, **_kw):
        if self.block is not None:
            raise self.block
        self.runs.append(shop_id)
        return await job(None)

    def proxy_for(self, shop_id):
        return self.proxy


@pytest.fixture
def scraped(monkeypatch):
    calls: list = []

    async def fake_scrape(profile_dir, proxy, registry=None):
        calls.append(proxy)
        return dict(SCRAPED)

    monkeypatch.setattr(shop_profile_mod, "scrape_platform_info", fake_scrape)
    return calls


def _shop(engine, entity=None) -> int:
    with engine.begin() as conn:
        return shop_store.create(conn, "店A", NOW, entity=entity)


def _svc(engine, runner, tmp_path):
    return ShopProfileService(engine, runner, profiles_dir=tmp_path)


async def test_scrape_saves_all_fields_and_entity_goes_to_shop(engine, tmp_path, scraped):
    sid = _shop(engine)
    runner = FakeRunner()
    await _svc(engine, runner, tmp_path).scrape_card(sid, actor="admin")
    assert runner.runs == [sid]
    assert scraped == ["http://p:1"]
    with engine.connect() as conn:
        profile = shop_profile_store.get(conn, sid)
        assert (profile["bank_name"], profile["bank_tail"], profile["platform_shop_id"]) == (
            "某某银行", "0001", "100000009")
        assert shop_store.get(conn, sid)["entity"] == "某某贸易有限公司"


async def test_scrape_keeps_hand_entered_entity(engine, tmp_path, scraped):
    sid = _shop(engine, entity="手填主体")
    await _svc(engine, FakeRunner(), tmp_path).scrape_card(sid, actor="admin")
    with engine.connect() as conn:
        assert shop_store.get(conn, sid)["entity"] == "手填主体"


async def test_scrape_writes_audit_without_values(engine, tmp_path, scraped):
    sid = _shop(engine)
    await _svc(engine, FakeRunner(), tmp_path).scrape_card(sid, actor="admin")
    with engine.connect() as conn:
        text = str(conn.exec_driver_sql("SELECT * FROM audit_log").fetchall())
    assert "shop.profile_scrape" in text and "admin" in text
    assert "0001" not in text and "100000009" not in text and "某某银行" not in text


@pytest.mark.parametrize("block", [
    ShopPaused(1, "risk:10011"),
    RuntimeError("该店铺尚未配置出口"),
])
async def test_scrape_blocked_by_runner_never_opens_browser(engine, tmp_path, scraped, block):
    sid = _shop(engine)
    with pytest.raises(type(block)):
        await _svc(engine, FakeRunner(block=block), tmp_path).scrape_card(sid, actor="admin")
    assert scraped == []
    with engine.connect() as conn:
        assert shop_profile_store.get(conn, sid) is None


async def _audit_rows(engine):
    import json

    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            "SELECT resp_summary, result FROM audit_log WHERE action = 'shop.profile_scrape'"
        ).fetchall()
    return [(json.loads(r[0]), r[1]) for r in rows]


async def test_scrape_drops_invalid_fields_and_audits_names(engine, tmp_path, monkeypatch):
    async def fake_scrape(profile_dir, proxy, registry=None):
        return {"bank_name": "示" * 51, "bank_tail": "１２３４",
                "platform_shop_id": "1" * 21, "entity": "某某贸易有限公司"}

    monkeypatch.setattr(shop_profile_mod, "scrape_platform_info", fake_scrape)
    sid = _shop(engine)
    info = await _svc(engine, FakeRunner(), tmp_path).scrape_card(sid, actor="admin")
    assert info == {"entity": "某某贸易有限公司"}
    with engine.connect() as conn:
        assert shop_profile_store.get(conn, sid) is None
    (resp, result), = await _audit_rows(engine)
    assert result == "ok"
    assert resp == {"fields": ["entity"],
                    "dropped": ["bank_name", "bank_tail", "platform_shop_id"]}


async def test_scrape_audit_skips_entity_not_written(engine, tmp_path, scraped):
    sid = _shop(engine, entity="手填主体")
    await _svc(engine, FakeRunner(), tmp_path).scrape_card(sid, actor="admin")
    (resp, _), = await _audit_rows(engine)
    assert resp == {"fields": ["bank_name", "bank_tail", "platform_shop_id"]}


async def test_scrape_failure_writes_error_audit_without_values(engine, tmp_path, monkeypatch):
    async def fake_scrape(profile_dir, proxy, registry=None):
        raise RuntimeError("secret http://u:p@203.0.113.5:1")

    monkeypatch.setattr(shop_profile_mod, "scrape_platform_info", fake_scrape)
    from app.domain.errors import InvalidRequest

    sid = _shop(engine)
    with pytest.raises(InvalidRequest):
        await _svc(engine, FakeRunner(), tmp_path).scrape_card(sid, actor="admin")
    (resp, result), = await _audit_rows(engine)
    assert result == "error" and resp == {"error": "InvalidRequest"}


async def test_scrape_unsupported_proxy_message_is_shown(engine, tmp_path, monkeypatch):
    from app.domain.errors import InvalidRequest

    async def fake_scrape(profile_dir, proxy, registry=None):
        raise ValueError("socks5 代理不支持账号密码")

    monkeypatch.setattr(shop_profile_mod, "scrape_platform_info", fake_scrape)
    sid = _shop(engine)
    with pytest.raises(InvalidRequest, match="socks5 代理不支持账号密码"):
        await _svc(engine, FakeRunner(), tmp_path).scrape_card(sid, actor="admin")
