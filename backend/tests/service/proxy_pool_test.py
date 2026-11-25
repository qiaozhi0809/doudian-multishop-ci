from datetime import UTC, datetime

import pytest
import sqlalchemy as sa

from app.domain.egress_rules import proxy_identity
from app.domain.errors import NotFound
from app.service.egress import EgressNotReady, EgressService, ProxyPoolInUse
from app.service.egress_probe import ProbeResult
from app.service.events import EventBus
from app.service.proxy_pool import MAX_IMPORT_LINES, ProxyPoolService
from app.shared.secret_box import DevKeyBox
from app.store import proxy_pool_store, shop_store
from app.store.schema import audit_log

T0 = datetime(2026, 12, 1, 0, 0, 0, tzinfo=UTC)
PW = "pw-not-in-ciphertext"
USER = "user-not-in-ciphertext"
URL_A = f"http://{USER}:{PW}@203.0.113.5:8000"


def good(i: int, expires: str = "2027-06-30") -> str:
    return f"203.0.113.{i}|8000|{USER}{i}|{PW}|{expires}"


async def _noop_probe(proxy):
    return ProbeResult(None, "network")


@pytest.fixture
def box(tmp_path):
    return DevKeyBox(tmp_path / "k")


@pytest.fixture
def svc(engine, box):
    return ProxyPoolService(engine, box, EventBus(), _noop_probe, clock=lambda: T0)


def _audit_text(engine) -> str:
    with engine.connect() as conn:
        rows = conn.execute(sa.select(audit_log)).mappings().all()
    return repr([dict(r) for r in rows])


def _count(engine) -> int:
    with engine.connect() as conn:
        return len(proxy_pool_store.list_with_usage(conn))


def _bind(engine, box, shop_name="店", status=None, url=URL_A) -> tuple[int, int]:
    """建店铺并通过 EgressService 绑定代理，返回 (shop_id, pool_id)。"""
    with engine.begin() as conn:
        sid = shop_store.create(conn, shop_name, "2026-11-25T00:00:00Z")
        if status:
            shop_store.set_status(conn, sid, status, "2026-11-25T00:00:00Z")
    egress = EgressService(engine, box, EventBus(), _fake_fetch, clock=lambda: T0)
    egress.set_egress(sid, "proxy", proxy_url=url)
    with engine.connect() as conn:
        return sid, shop_store.get(conn, sid)["proxy_pool_id"]


async def _fake_fetch(proxy):
    return None


def test_import_partial_failure_reports_line_numbers(svc, engine):
    text = "\n".join(good(i) if i not in (3, 7) else "bad|line" for i in range(1, 11))
    s = svc.import_text(text, "admin")
    assert (s.added, s.skipped, s.failed) == (8, 0, 2)
    assert [n for n, _ in s.failures] == [3, 7]
    assert PW not in repr(s) and PW not in _audit_text(engine)
    assert "bad|line" not in repr(s)


def test_import_twice_and_in_batch_duplicates_skipped(svc, engine):
    s = svc.import_text(f"{good(1)}\n{good(1)}", "admin")
    assert (s.added, s.skipped, s.failed) == (1, 1, 0)
    s = svc.import_text(f"{good(1)}\n{good(2)}", "admin")
    assert (s.added, s.skipped, s.failed) == (1, 1, 0)
    s = svc.import_text(f"{good(1)}\n{good(2)}", "admin")
    assert (s.added, s.skipped) == (0, 2)
    assert _count(engine) == 2


def test_import_blank_lines_ignored_and_over_limit_rejected(svc, engine):
    s = svc.import_text(f"\n\n{good(1)}\n   \n{good(2)}\n", "admin")
    assert s.added == 2 and s.failed == 0
    # 空行不计入上限；行号按原文行计
    s = svc.import_text(f"\nbad\n{good(3)}", "admin")
    assert s.failures[0][0] == 2
    too_many = "\n".join(good(i % 250 + 1, f"2027-01-{i // 250 + 1:02d}")
                         for i in range(MAX_IMPORT_LINES + 1))
    with pytest.raises(ValueError):
        svc.import_text(too_many, "admin")
    assert _count(engine) == 3
    ok = "\n\n".join(["x"] * MAX_IMPORT_LINES)  # 恰好 500 个非空行，不超限
    assert svc.import_text(ok, "admin").failed == MAX_IMPORT_LINES


def test_import_audit_records_counts(svc, engine):
    svc.import_text(f"{good(1)}\nbad", "admin")
    text = _audit_text(engine)
    assert "proxy_pool.import" in text and "admin" in text


def test_delete_in_use_by_enabled_shop_conflicts(svc, engine, box):
    _, pool_id = _bind(engine, box, shop_name="占用店")
    with pytest.raises(ProxyPoolInUse) as e:
        svc.delete(pool_id, "admin")
    assert "占用店" in str(e.value)
    assert _count(engine) == 1


def test_delete_only_disabled_referrer_unbinds_it(svc, engine, box):
    sid, pool_id = _bind(engine, box, status="disabled")
    svc.delete(pool_id, "admin")
    assert _count(engine) == 0
    with engine.connect() as conn:
        assert shop_store.get(conn, sid)["proxy_pool_id"] is None
    egress = EgressService(engine, box, EventBus(), _fake_fetch, clock=lambda: T0)
    with pytest.raises(EgressNotReady, match="代理地址缺失"):
        egress.proxy_for(sid)


def test_delete_free_and_missing(svc, engine):
    svc.import_text(good(1), "admin")
    with engine.connect() as conn:
        pid = proxy_pool_store.list_with_usage(conn)[0]["id"]
    svc.delete(pid, "admin")
    assert _count(engine) == 0
    with pytest.raises(NotFound):
        svc.delete(pid, "admin")


def test_list_view_hides_disabled_user_and_marks_expired(svc, engine, box):
    svc.import_text(f"{good(1, '2026-01-01')}\n{good(2)}", "admin")
    sid, _ = _bind(engine, box, shop_name="停用店", status="disabled")
    _bind(engine, box, shop_name="启用店", url="http://a:b@203.0.113.2:8000")
    view = svc.list_view()
    by_display = {v["proxy_display"]: v for v in view}
    assert by_display["203.0.113.1:8000"]["expiry_state"] == "expired"
    assert by_display["203.0.113.1:8000"]["in_use_by"] is None
    # 停用店铺不算占用；启用店铺 203.0.113.2 与导入项 identity 不同（账号不同），各自成项
    assert any(v["in_use_by"] and v["in_use_by"]["shop_name"] == "启用店" for v in view)
    assert not any(v["in_use_by"] and v["in_use_by"]["shop_name"] == "停用店" for v in view)
    assert set(view[0]) == {
        "id", "proxy_display", "expires_at", "expiry_state", "in_use_by",
        "last_checked_at", "last_check_ip",
    }
    assert PW not in repr(view)
    assert sid


def _legacy(engine, box, url=URL_A) -> int:
    with engine.begin() as conn:
        return proxy_pool_store.upsert(
            conn, identity="legacy:1", proxy_url=box.encrypt(url.encode()),
            proxy_display="203.0.113.5:8000", expires_at=None, now="2026-11-25T00:00:00Z")


def test_rehash_legacy_sets_real_identity(svc, engine, box):
    pid = _legacy(engine, box)
    assert svc.rehash_legacy() == 1
    with engine.connect() as conn:
        assert proxy_pool_store.get(conn, pid)["identity"] == proxy_identity(URL_A)
    assert svc.rehash_legacy() == 0


def test_rehash_legacy_keeps_placeholder_on_clash(svc, engine, box):
    with engine.begin() as conn:
        proxy_pool_store.upsert(
            conn, identity=proxy_identity(URL_A), proxy_url=box.encrypt(URL_A.encode()),
            proxy_display="203.0.113.5:8000", expires_at=None, now="2026-11-25T00:00:00Z")
    pid = _legacy(engine, box)
    assert svc.rehash_legacy() == 0
    with engine.connect() as conn:
        assert proxy_pool_store.get(conn, pid)["identity"] == "legacy:1"
