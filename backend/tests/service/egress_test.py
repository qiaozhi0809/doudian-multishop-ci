from datetime import UTC, datetime, timedelta

import pytest

from app.adapter.doudian.errors import EgressUnavailable
from app.domain.egress_rules import proxy_identity
from app.domain.errors import NotFound
from app.service.egress import EgressConflict, EgressNotReady, EgressService, ProxyPoolInUse
from app.service.events import EventBus
from app.service.shop_admin import REENABLE_CONFLICT, ShopAdminService
from app.shared.logging_setup import configure_logging
from app.shared.secret_box import DevKeyBox
from app.store import proxy_pool_store, shop_store

T0 = datetime(2026, 12, 1, 0, 0, 0, tzinfo=UTC)
# 假账号密码要足够长：太短的子串（如 "u1"）可能偶然出现在随机 base64 密文里
USER_A, USER_B = "user-a-not-in-ciphertext", "user-b-not-in-ciphertext"
PW = "pw-not-in-ciphertext"
URL_A = f"http://{USER_A}:{PW}@203.0.113.5:8000"
URL_B = f"http://{USER_B}:{PW}@203.0.113.6:8000"


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
    with pytest.raises(NotFound):
        env.svc.set_egress(999, "direct")


def test_set_egress_paste(env):
    sid = env.shop()
    env.svc.set_egress(sid, "proxy", paste=f"203.0.113.5|8000|{USER_A}|{PW}|2026-12-25")
    row = env.row(sid)
    assert row["proxy_expires_at"] == "2026-12-25"
    assert row["proxy_display"] == "203.0.113.5:8000"
    assert env.svc.proxy_for(sid) == URL_A
    env.svc.set_egress(sid, "proxy", paste=f"203.0.113.5|8000|{USER_A}|{PW}|2026-12-25",
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


# ---- 从池选代理 ----

def _pool_item(env, url=URL_A, expires_at=None) -> int:
    with env.engine.begin() as conn:
        return proxy_pool_store.upsert(
            conn, identity=proxy_identity(url), proxy_url=env.box.encrypt(url.encode()),
            proxy_display="203.0.113.5:8000", expires_at=expires_at,
            now="2026-11-25T00:00:00Z")


def test_bind_pool_item(env):
    sid, pid = env.shop(), _pool_item(env)
    env.svc.set_egress(sid, "proxy", pool_id=pid)
    row = env.row(sid)
    assert row["proxy_pool_id"] == pid and row["egress_status"] == "unchecked"
    assert env.svc.proxy_for(sid) == URL_A


def test_bind_item_used_by_enabled_shop_conflicts(env):
    a, b, pid = env.shop("店A"), env.shop("店B"), _pool_item(env)
    env.svc.set_egress(a, "proxy", pool_id=pid)
    with pytest.raises(ProxyPoolInUse, match="店A"):
        env.svc.set_egress(b, "proxy", pool_id=pid)
    assert env.row(b)["proxy_pool_id"] is None
    env.svc.set_egress(a, "proxy", pool_id=pid)  # 自己重绑不算冲突


def test_bind_item_used_only_by_disabled_shop_ok(env):
    a, b, pid = env.shop("店A"), env.shop("店B"), _pool_item(env)
    env.svc.set_egress(a, "proxy", pool_id=pid)
    with env.engine.begin() as conn:
        shop_store.set_status(conn, a, "disabled", "2026-11-25T00:00:00Z")
    env.svc.set_egress(b, "proxy", pool_id=pid)
    assert env.row(b)["proxy_pool_id"] == pid


def test_bind_expired_item_rejected(env):
    sid, pid = env.shop(), _pool_item(env, expires_at="2026-11-30")
    with pytest.raises(ValueError, match="代理已到期，请续费或更换"):
        env.svc.set_egress(sid, "proxy", pool_id=pid)
    assert env.row(sid)["proxy_pool_id"] is None


def test_bind_missing_item_not_found(env):
    with pytest.raises(NotFound):
        env.svc.set_egress(env.shop(), "proxy", pool_id=999)


def test_more_than_one_entry_rejected(env):
    sid, pid = env.shop(), _pool_item(env)
    with pytest.raises(ValueError):
        env.svc.set_egress(sid, "proxy", pool_id=pid, paste=f"203.0.113.5|8000|{USER_A}|{PW}")
    with pytest.raises(ValueError):
        env.svc.set_egress(sid, "proxy", pool_id=pid, proxy_url=URL_A)
    with pytest.raises(ValueError):
        env.svc.set_egress(sid, "direct", pool_id=pid)


def test_paste_existing_proxy_reuses_item_and_updates_expiry(env):
    sid, pid = env.shop(), _pool_item(env, expires_at="2027-01-01")
    env.svc.set_egress(sid, "proxy", paste=f"203.0.113.5|8000|{USER_A}|{PW}|2027-02-02")
    row = env.row(sid)
    assert row["proxy_pool_id"] == pid and row["proxy_expires_at"] == "2027-02-02"
    with env.engine.connect() as conn:
        assert len(proxy_pool_store.list_with_usage(conn)) == 1


def test_paste_proxy_used_by_other_shop_conflicts(env):
    a, b = env.shop("店A"), env.shop("店B")
    env.svc.set_egress(a, "proxy", proxy_url=URL_A)
    with pytest.raises(ProxyPoolInUse, match="店A"):
        env.svc.set_egress(b, "proxy", proxy_url=URL_A)


def test_race_on_same_item_maps_to_conflict(env, monkeypatch):
    a, b, pid = env.shop("店A"), env.shop("店B"), _pool_item(env)
    env.svc.set_egress(a, "proxy", pool_id=pid)
    # 模拟「预检之后才被抢先绑定」：让预检看不到占用，写入时撞 uq_shop_pool
    monkeypatch.setattr(EgressService, "_ensure_pool_free", staticmethod(lambda *a: None))
    with pytest.raises(ProxyPoolInUse):
        env.svc.set_egress(b, "proxy", pool_id=pid)
    assert env.row(b)["proxy_pool_id"] is None


def test_reenable_when_item_taken_says_proxy_in_use(env):
    a, b, pid = env.shop("店A"), env.shop("店B"), _pool_item(env)
    env.svc.set_egress(a, "proxy", pool_id=pid)
    with env.engine.begin() as conn:
        shop_store.set_status(conn, a, "disabled", "2026-11-25T00:00:00Z")
    env.svc.set_egress(b, "proxy", pool_id=pid)
    admin = ShopAdminService(env.engine, env.events, clock=lambda: env.now)
    with pytest.raises(EgressConflict, match="代理已被占用") as ei:
        admin.update(a, enabled=True)
    assert str(ei.value) == REENABLE_CONFLICT
    assert env.row(a)["status"] == "disabled"


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
    for secret in (PW, USER_A, URL_A, "203.0.113.5:8000"):
        assert secret.encode() not in blob
    assert env.box.decrypt(blob).decode() == URL_A  # 解密后就是原 URL
    assert env.row(sid)["proxy_display"] == "203.0.113.5:8000"
    assert PW not in capsys.readouterr().out
    assert env.svc.proxy_for(sid) == URL_A


async def test_proxy_mode_without_url_never_probes_direct(env):
    sid = await _ready_shop(env)
    env.fetch_calls.clear()
    with env.engine.begin() as conn:  # 模拟数据异常或手工改库
        shop_store.set_egress(conn, sid, "2026-12-01T00:00:00Z", proxy_pool_id=None)
    env.now += timedelta(minutes=11)
    for call in (env.svc.check(sid), env.svc.ensure_ready(sid)):
        with pytest.raises(EgressNotReady, match="代理地址缺失"):
            await call
    with pytest.raises(EgressNotReady):
        env.svc.proxy_for(sid)
    assert env.fetch_calls == []


async def test_unreachable_message_does_not_claim_paused(env):
    sid = await _ready_shop(env)
    env.now += timedelta(minutes=11)
    env.ips[URL_A] = None
    with pytest.raises(EgressUnavailable, match="代理是否到期"):
        await env.svc.ensure_ready(sid)
