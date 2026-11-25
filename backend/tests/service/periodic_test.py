
from app.adapter.browser.login import LoginResult
from app.service.events import EventBus
from app.service.periodic import for_each_active_shop, probe_session
from app.service.session_manager import SessionManager
from app.shared.secret_box import DevKeyBox
from app.store import shop_store

NOW = "2026-11-25T00:00:00Z"


def _make_shops(engine, mgr):
    with engine.begin() as conn:
        ids = [shop_store.create(conn, n, NOW) for n in "ABCD"]
    login = LoginResult([], "tok_" + "x" * 8, "2027-01-24T00:00:00Z", {})
    for sid in ids[:3]:
        mgr.save_login(sid, login)  # 前三家 active，D 仍是 needs_login
    with engine.begin() as conn:
        shop_store.set_paused(conn, ids[2], "risk_blocked:602502151", NOW)
    return ids


async def test_for_each_active_shop_skips_paused_and_inactive(engine, tmp_path):
    mgr = SessionManager(engine, DevKeyBox(tmp_path / "k"), EventBus())
    ids = _make_shops(engine, mgr)
    seen = []

    async def fn(shop_id):
        seen.append(shop_id)

    await for_each_active_shop(engine, fn)
    assert seen == [ids[0], ids[1]]


async def test_single_shop_failure_does_not_affect_others(engine, tmp_path):
    mgr = SessionManager(engine, DevKeyBox(tmp_path / "k"), EventBus())
    ids = _make_shops(engine, mgr)
    seen = []

    async def fn(shop_id):
        seen.append(shop_id)
        if shop_id == ids[0]:
            raise RuntimeError("boom")

    await for_each_active_shop(engine, fn)
    assert sorted(seen) == [ids[0], ids[1]]


async def test_probe_session_calls_tabcnt_as_system():
    calls = []

    class FakeRunner:
        async def run(self, shop_id, job, *, actor, needs_session=True):
            calls.append((shop_id, actor, needs_session))

    await probe_session(FakeRunner(), 7)
    assert calls == [(7, "system", True)]
