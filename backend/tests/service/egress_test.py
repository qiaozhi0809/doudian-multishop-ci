from datetime import UTC, datetime, timedelta

import pytest

from app.adapter.doudian.errors import EgressUnavailable
from app.service.egress import EgressConflict, EgressNotReady, EgressService
from app.service.events import EventBus
from app.shared.logging_setup import configure_logging
from app.shared.secret_box import DevKeyBox
from app.store import shop_store

T0 = datetime(2026, 12, 1, 0, 0, 0, tzinfo=UTC)
PW = "secretpw"
URL_A = f"http://u1:{PW}@203.0.113.5:8000"
URL_B = f"http://u2:{PW}@203.0.113.6:8000"


class Env:
    def __init__(self, engine, tmp_path):
        self.engine = engine
        self.now = T0
        self.ips: dict[str | None, str | None] = {}
        self.fetch_calls: list[str | None] = []
        self.events = EventBus()
        self.box = DevKeyBox(tmp_path / "k")
        self.svc = EgressService(
            engine, self.box, self.events, self._fetch, clock=lambda: self.now
        )

    async def _fetch(self, proxy):
        self.fetch_calls.append(proxy)
        return self.ips.get(proxy)

    def shop(self, name="店", minute=0, status=None) -> int:
        created = f"2026-11-25T00:{minute:02d}:00Z"
        with self.engine.begin() as conn:
            sid = shop_store.create(conn, name, created)
            if status:
                shop_store.set_status(conn, sid, status, created)
        return sid

    def row(self, shop_id):
        with self.engine.connect() as conn:
            return shop_store.get(conn, shop_id)


@pytest.fixture
def env(engine, tmp_path):
    return Env(engine, tmp_path)


async def _ready_shop(env, url=URL_A, ip="203.0.113.5", **kw) -> int:
    sid = env.shop(**kw)
    env.svc.set_egress(sid, "proxy", proxy_url=url)
    env.ips[url] = ip
    await env.svc.check(sid)
    return sid


# ---- 设置出口 ----

def test_set_egress_validates(env):
    sid = env.shop()
    with pytest.raises(ValueError):
        env.svc.set_egress(sid, "proxy", proxy_url="socks5://u:p@203.0.113.5:1080")
    with pytest.raises(ValueError):
        env.svc.set_egress(sid, "proxy")
    with pytest.raises(ValueError):
        env.svc.set_egress(sid, "bogus")
    with pytest.raises(LookupError):
        env.svc.set_egress(999, "direct")


def test_set_egress_paste(env):
    sid = env.shop()
    env.svc.set_egress(sid, "proxy", paste=f"203.0.113.5|8000|u1|{PW}|2026-12-25")
    row = env.row(sid)
    assert row["proxy_expires_at"] == "2026-12-25"
    assert row["proxy_display"] == "203.0.113.5:8000"
    assert env.svc.proxy_for(sid) == URL_A
    env.svc.set_egress(sid, "proxy", paste=f"203.0.113.5|8000|u1|{PW}|2026-12-25",
                       expires_at="2027-01-31")
    assert env.row(sid)["proxy_expires_at"] == "2027-01-31"


def test_second_direct_conflict(env):
    a, b = env.shop("A"), env.shop("B")
    env.svc.set_egress(a, "direct")
    with pytest.raises(EgressConflict):
        env.svc.set_egress(b, "direct")
    env.svc.set_egress(a, "direct")  # 自己重复设置不算冲突
    assert env.row(b)["egress_mode"] is None


def test_disabled_shop_does_not_block_direct(env):
    a, b = env.shop("A"), env.shop("B")
    env.svc.set_egress(a, "direct")
    with env.engine.begin() as conn:
        shop_store.set_status(conn, a, "disabled", "2026-11-25T00:00:00Z")
    env.svc.set_egress(b, "direct")


async def test_change_proxy_resets_and_requires_relogin(env):
    sid = await _ready_shop(env, status="active")
    assert env.row(sid)["egress_ip"] == "203.0.113.5"
    sub = env.events.subscribe()
    env.svc.set_egress(sid, "proxy", proxy_url=URL_B)
    row = env.row(sid)
    assert row["egress_ip"] is None and row["egress_status"] == "unchecked"
    assert row["egress_ip_pending"] is None and row["status"] == "needs_login"
    event, data = await anext(sub)
    assert event == "shop_status_changed"
    assert data["shop_id"] == sid and data["status"] == "needs_login"


# ---- 出口检查 ----

async def test_check_ok_writes_ip(env):
    sid = await _ready_shop(env)
    row = env.row(sid)
    assert (row["egress_status"], row["egress_ip"]) == ("ok", "203.0.113.5")
    assert row["egress_checked_at"] == "2026-12-01T00:00:00Z"


async def test_direct_mode_probes_without_proxy(env):
    sid = env.shop()
    env.svc.set_egress(sid, "direct")
    env.ips[None] = "203.0.113.50"
    st = await env.svc.check(sid)
    assert st.egress_status == "ok" and env.fetch_calls == [None]
    assert env.svc.proxy_for(sid) is None


async def test_unreachable_keeps_old_ip(env):
    sid = await _ready_shop(env)
    env.ips[URL_A] = None
    st = await env.svc.check(sid)
    assert st.egress_status == "unreachable" and st.egress_ip == "203.0.113.5"


async def test_changed_keeps_old_ip_until_accepted(env):
    sid = await _ready_shop(env)
    env.ips[URL_A] = "203.0.113.77"
    st = await env.svc.check(sid)
    assert st.egress_status == "changed"
    assert (st.egress_ip, st.egress_ip_pending) == ("203.0.113.5", "203.0.113.77")
    st = await env.svc.check(sid, accept_change=True)
    assert (st.egress_status, st.egress_ip, st.egress_ip_pending) == (
        "ok", "203.0.113.77", None)


async def test_duplicate_later_shop_paused_no_integrity_error(env):
    first = await _ready_shop(env, url=URL_A, ip="203.0.113.5", name="先", minute=0)
    later = env.shop("后", minute=1)
    env.svc.set_egress(later, "proxy", proxy_url=URL_B)
    env.ips[URL_B] = "203.0.113.5"  # 与先建的店相同
    st = await env.svc.check(later)
    assert st.egress_status == "duplicate"
    assert st.egress_ip is None and st.egress_ip_pending == "203.0.113.5"
    assert env.row(first)["egress_status"] == "ok"
    with pytest.raises(EgressNotReady):
        await env.svc.ensure_ready(later)


async def test_duplicate_detected_from_earlier_shop_demotes_later(env):
    earlier = env.shop("先", minute=0)
    later = await _ready_shop(env, url=URL_B, ip="203.0.113.5", name="后", minute=1)
    env.svc.set_egress(earlier, "proxy", proxy_url=URL_A)
    env.ips[URL_A] = "203.0.113.5"
    st = await env.svc.check(earlier)
    assert (st.egress_status, st.egress_ip) == ("ok", "203.0.113.5")
    demoted = env.row(later)
    assert demoted["egress_status"] == "duplicate" and demoted["egress_ip"] is None
    assert demoted["egress_ip_pending"] == "203.0.113.5"


async def test_unconfigured_not_ready(env):
    sid = env.shop()
    with pytest.raises(EgressNotReady):
        await env.svc.check(sid)
    with pytest.raises(EgressNotReady):
        await env.svc.ensure_ready(sid)
    assert env.fetch_calls == []


# ---- ensure_ready ----

async def test_ensure_ready_unreachable_raises(env):
    sid = await _ready_shop(env)
    env.now += timedelta(minutes=11)
    env.ips[URL_A] = None
    with pytest.raises(EgressUnavailable):
        await env.svc.ensure_ready(sid)


async def test_ensure_ready_cached_10_min(env):
    sid = await _ready_shop(env)
    assert len(env.fetch_calls) == 1
    env.now += timedelta(minutes=9)
    await env.svc.ensure_ready(sid)
    assert len(env.fetch_calls) == 1
    env.now += timedelta(minutes=2)  # 距上次检查 11 分钟
    await env.svc.ensure_ready(sid)
    assert len(env.fetch_calls) == 2


async def test_ensure_ready_changed_raises_not_ready(env):
    sid = await _ready_shop(env)
    env.now += timedelta(minutes=11)
    env.ips[URL_A] = "203.0.113.77"
    with pytest.raises(EgressNotReady):
        await env.svc.ensure_ready(sid)


async def test_expired_proxy_not_ready(env):
    sid = env.shop()
    env.svc.set_egress(sid, "proxy", proxy_url=URL_A, expires_at="2026-11-30")
    env.ips[URL_A] = "203.0.113.5"
    with pytest.raises(EgressNotReady):
        await env.svc.ensure_ready(sid)
    with pytest.raises(EgressNotReady):
        await env.svc.check(sid)
    assert env.fetch_calls == []  # 到期的代理不发任何请求


# ---- 凭证保护 ----

async def test_proxy_url_encrypted_and_not_logged(env, capsys):
    configure_logging(json=True)
    sid = await _ready_shop(env)
    env.ips[URL_A] = None
    await env.svc.check(sid)
    blob = env.row(sid)["proxy_url"]
    assert PW.encode() not in blob and b"u1" not in blob
    assert env.row(sid)["proxy_display"] == "203.0.113.5:8000"
    assert PW not in capsys.readouterr().out
    assert env.svc.proxy_for(sid) == URL_A
