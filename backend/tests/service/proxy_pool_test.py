import json

import pytest
import sqlalchemy as sa
import structlog.testing

from app.domain.egress_rules import proxy_identity
from app.domain.errors import NotFound
from app.service.egress import EgressNotReady, EgressService, ProxyPoolInUse
from app.service.events import EventBus
from app.service.proxy_pool import MAX_IMPORT_LINES
from app.store import proxy_pool_store, shop_store
from app.store.schema import audit_log
from tests.service.proxy_pool_support import (
    PW,
    T0,
    URL_A,
    USER,
    audit_text,
    bind,
    box,  # noqa: F401  (夹具)
    count,
    fake_fetch,
    good,
    svc,  # noqa: F401  (夹具)
)


def test_import_partial_failure_reports_line_numbers(svc, engine):
    text = "\n".join(good(i) if i not in (3, 7) else "bad|line" for i in range(1, 11))
    s = svc.import_text(text, "admin")
    assert (s.added, s.skipped, s.failed) == (8, 0, 2)
    assert [n for n, _ in s.failures] == [3, 7]
    assert PW not in repr(s) and PW not in audit_text(engine)
    assert "bad|line" not in repr(s)


def test_import_host_with_at_sign_fails_and_stores_nothing(svc, engine):
    s = svc.import_text(f"a@203.0.113.9|8000|{USER}|{PW}|2027-06-30", "admin")
    assert (s.added, s.failed) == (0, 1)
    assert s.failures == [(1, "代理主机格式不正确")]
    assert count(engine) == 0
    assert PW not in repr(s) and PW not in audit_text(engine)


def test_import_twice_and_in_batch_duplicates_skipped(svc, engine):
    s = svc.import_text(f"{good(1)}\n{good(1)}", "admin")
    assert (s.added, s.skipped, s.failed) == (1, 1, 0)
    s = svc.import_text(f"{good(1)}\n{good(2)}", "admin")
    assert (s.added, s.skipped, s.failed) == (1, 1, 0)
    s = svc.import_text(f"{good(1)}\n{good(2)}", "admin")
    assert (s.added, s.skipped) == (0, 2)
    assert count(engine) == 2


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
    assert count(engine) == 3
    ok = "\n\n".join(["x"] * MAX_IMPORT_LINES)  # 恰好 500 个非空行，不超限
    assert svc.import_text(ok, "admin").failed == MAX_IMPORT_LINES


def test_import_audit_records_counts(svc, engine):
    svc.import_text(f"{good(1)}\nbad\n{good(1)}\nbad2", "admin")
    with engine.connect() as conn:
        row = conn.execute(sa.select(audit_log)).mappings().one()
    assert row["action"] == "proxy_pool.import" and row["actor"] == "admin"
    assert json.loads(row["resp_summary"]) == {
        "added": 1, "skipped": 1, "failed": 2, "failed_lines": [2, 4]}
    assert json.loads(row["req_summary"]) == {"lines": 4}
    assert PW not in repr(dict(row))


def test_import_line_numbers_match_editor_with_cr_and_odd_separators(svc):
    # splitlines() 会把 \x0b \x0c \x1c 等也当换行，行号与编辑器对不上
    text = f"{good(1)}\r\nbad\x0bstill-line2\r\n{good(3)}\r\nbad4\r\n"
    s = svc.import_text(text, "admin")
    assert [n for n, _ in s.failures] == [2, 4]
    assert s.added == 2


def test_delete_in_use_by_enabled_shop_conflicts(svc, engine, box):
    _, pool_id = bind(engine, box, shop_name="占用店")
    with pytest.raises(ProxyPoolInUse) as e:
        svc.delete(pool_id, "admin")
    assert "占用店" in str(e.value)
    assert count(engine) == 1


def test_delete_only_disabled_referrer_unbinds_it(svc, engine, box):
    sid, pool_id = bind(engine, box, status="disabled")
    svc.delete(pool_id, "admin")
    assert count(engine) == 0
    with engine.connect() as conn:
        assert shop_store.get(conn, sid)["proxy_pool_id"] is None
    egress = EgressService(engine, box, EventBus(), fake_fetch, clock=lambda: T0)
    with pytest.raises(EgressNotReady, match="代理地址缺失"):
        egress.proxy_for(sid)


def test_delete_free_and_missing(svc, engine):
    svc.import_text(good(1), "admin")
    with engine.connect() as conn:
        pid = proxy_pool_store.list_with_usage(conn)[0]["id"]
    svc.delete(pid, "admin")
    assert count(engine) == 0
    with pytest.raises(NotFound):
        svc.delete(pid, "admin")


def test_list_view_hides_disabled_user_and_marks_expired(svc, engine, box):
    svc.import_text(f"{good(1, '2026-01-01')}\n{good(2)}", "admin")
    sid, _ = bind(engine, box, shop_name="停用店", status="disabled")
    bind(engine, box, shop_name="启用店", url="http://a:b@203.0.113.2:8000")
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


def legacy(engine, box, url=URL_A) -> int:
    with engine.begin() as conn:
        return proxy_pool_store.upsert(
            conn, identity="legacy:1", proxy_url=box.encrypt(url.encode()),
            proxy_display="203.0.113.5:8000", expires_at=None, now="2026-11-25T00:00:00Z")


def test_rehash_legacy_sets_real_identity(svc, engine, box):
    pid = legacy(engine, box)
    assert svc.rehash_legacy() == 1
    with engine.connect() as conn:
        assert proxy_pool_store.get(conn, pid)["identity"] == proxy_identity(URL_A)
    assert svc.rehash_legacy() == 0


def test_rehash_legacy_keeps_placeholder_on_clash(svc, engine, box):
    with engine.begin() as conn:
        proxy_pool_store.upsert(
            conn, identity=proxy_identity(URL_A), proxy_url=box.encrypt(URL_A.encode()),
            proxy_display="203.0.113.5:8000", expires_at=None, now="2026-11-25T00:00:00Z")
    pid = legacy(engine, box)
    assert svc.rehash_legacy() == 0
    with engine.connect() as conn:
        assert proxy_pool_store.get(conn, pid)["identity"] == "legacy:1"


def test_rehash_legacy_decrypt_failure_does_not_abort(svc, engine, box):
    bad = legacy(engine, box)
    with engine.begin() as conn:
        proxy_pool_store.update(conn, bad, "2026-11-25T00:00:00Z", proxy_url=b"garbage")
        good_id = proxy_pool_store.upsert(
            conn, identity="legacy:2", proxy_url=box.encrypt(URL_A.encode()),
            proxy_display="203.0.113.5:8000", expires_at=None, now="2026-11-25T00:00:00Z")
    with structlog.testing.capture_logs() as logs:
        assert svc.rehash_legacy() == 1
    with engine.connect() as conn:
        assert proxy_pool_store.get(conn, good_id)["identity"] == proxy_identity(URL_A)
        assert proxy_pool_store.get(conn, bad)["identity"] == "legacy:1"
    ev = [x for x in logs if x["event"] == "proxy_pool.rehash_decrypt_failed"]
    assert len(ev) == 1 and ev[0]["pool_id"] == bad
    assert set(ev[0]) <= {"event", "pool_id", "log_level"}


