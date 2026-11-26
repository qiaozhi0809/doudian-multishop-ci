"""计数卡快捷筛选（在 SQL 里筛完再分页）与状态列按界面顺序排序。"""

import json
from dataclasses import replace

from app.domain.order_status import LocalOrderStatus
from app.store import aftersale_store, catalog_store, order_store, reconcile_store, shop_store
from tests.store.aggregate_stores_test import aftersale, product, stock
from tests.store.builders import make_order
from tests.store.conftest import NOW

T_NOW = "2026-11-26T00:00:00Z"
T_24H = "2026-11-27T00:00:00Z"


def _shop(engine, name="店A") -> int:
    with engine.begin() as conn:
        return shop_store.create(conn, name, NOW)


def _nos(rows, key="order_no"):
    return [r[key] for r in rows]


# ---- 订单 ----


def _pay(minute: int) -> str:
    return f"2026-11-24T10:{minute:02d}:00Z"


def _orders(engine, sid):
    with engine.begin() as conn:
        order_store.upsert_orders(conn, sid, [
            make_order("late", exp_ship_time="2026-11-25T12:00:00Z", pay_time=_pay(4)),
            make_order("soon", exp_ship_time="2026-11-26T10:00:00Z", pay_time=_pay(3)),
            make_order("later", exp_ship_time="2026-11-28T10:00:00Z", pay_time=_pay(2)),
            make_order("done", platform_status=3, exp_ship_time="2026-11-25T00:00:00Z",
                       pay_time=_pay(1)),
        ], NOW)


def _list_orders(engine, sid, quick, **kw):
    with engine.connect() as conn:
        return order_store.list_orders(
            conn, [sid], kw.pop("status", None), kw.pop("page", 1), kw.pop("page_size", 50),
            kw.pop("sort", None), kw.pop("order", "asc"), quick=quick, now=T_NOW, in_24h=T_24H)


def test_order_quick_filters(engine):
    sid = _shop(engine)
    _orders(engine, sid)
    assert _nos(_list_orders(engine, sid, "stock_up")[0]) == ["late", "soon", "later"]
    assert _nos(_list_orders(engine, sid, "exp_ship")[0]) == ["soon"]
    assert _nos(_list_orders(engine, sid, "ship_delay")[0]) == ["late"]


def test_order_quick_filter_in_aftersale_uses_open_aftersales(engine):
    sid = _shop(engine)
    _orders(engine, sid)
    with engine.begin() as conn:
        aftersale_store.upsert_aftersales(conn, sid, [
            replace(aftersale("1", deadline="2026-11-28T00:00:00Z"), order_no="soon"),
            replace(aftersale("2", deadline=None), order_no="later"),  # 已完结的不算
        ], NOW)
    rows, total = _list_orders(engine, sid, "in_aftersale")
    assert _nos(rows) == ["soon"] and total == 1


def test_order_quick_filter_combines_with_status_sort_and_paging(engine):
    sid = _shop(engine)
    _orders(engine, sid)
    with engine.begin() as conn:
        order_store.set_local_status(conn, sid, "later", LocalOrderStatus.PRINTED, NOW)
    rows, total = _list_orders(engine, sid, "stock_up", sort="pay_time", order="asc",
                               page=1, page_size=2)
    assert total == 3 and _nos(rows) == ["later", "soon"]
    rows, total = _list_orders(engine, sid, "stock_up", status=LocalOrderStatus.PRINTED)
    assert total == 1 and _nos(rows) == ["later"]


def test_order_status_sorts_by_display_order(engine):
    sid = _shop(engine)
    with engine.begin() as conn:
        order_store.upsert_orders(conn, sid, [make_order(n) for n in ("a", "b", "c", "d")], NOW)
        # 代码字典序：exception < label_obtained < printed < synced
        # 界面顺序：待处理 → 已打单 → 已打印 → 异常
        order_store.set_local_status(conn, sid, "a", LocalOrderStatus.EXCEPTION, NOW)
        order_store.set_local_status(conn, sid, "b", LocalOrderStatus.PRINTED, NOW)
        order_store.set_local_status(conn, sid, "c", LocalOrderStatus.LABEL_OBTAINED, NOW)
    rows, _ = _list_orders(engine, sid, None, sort="status", order="asc")
    assert [r["status"] for r in rows] == ["synced", "label_obtained", "printed", "exception"]


def test_order_platform_status_sorts_by_fulfilment_order(engine):
    sid = _shop(engine)
    with engine.begin() as conn:
        order_store.upsert_orders(conn, sid, [
            make_order("closed", platform_status=4), make_order("done", platform_status=5),
            make_order("odd", platform_status=9), make_order("up", platform_status=2),
            make_order("none", platform_status=None),
        ], NOW)
    rows, _ = _list_orders(engine, sid, None, sort="platform_status", order="asc")
    # 待发货 → 已完成 → 已关闭 → 未确认的码 → 空
    assert _nos(rows) == ["up", "done", "closed", "odd", "none"]


# ---- 商品 ----


def _products(engine, sid):
    with engine.begin() as conn:
        catalog_store.upsert_products(conn, sid, [
            product("p-forbidden", tab="forbidden", name="甲"),
            product("p-on", tab="onSale", name="乙"),
            product("p-draft", tab="draft", name="甲乙"),
            product("p-unpass", tab="unpass_new", name="丙"),
            product("p-off", tab="已下架", name="戊"),
            product("p-sell", tab="售卖中", name="己"),
            product("p-none", tab=None, name="丁"),
        ], NOW)


def test_product_quick_filter_matches_tab_aliases(engine):
    sid = _shop(engine)
    _products(engine, sid)
    with engine.connect() as conn:
        on, total = catalog_store.list_products(conn, [sid], quick="onsale")
        assert sorted(_nos(on, "product_id")) == ["p-on", "p-sell"] and total == 2
        off, _ = catalog_store.list_products(conn, [sid], quick="forbidden")
        assert sorted(_nos(off, "product_id")) == ["p-forbidden", "p-off"]
        unpass, _ = catalog_store.list_products(conn, [sid], quick="unpass")
        assert _nos(unpass, "product_id") == ["p-unpass"]


def test_product_quick_filter_combines_with_keyword_and_sort(engine):
    sid = _shop(engine)
    _products(engine, sid)
    with engine.begin() as conn:
        catalog_store.upsert_products(conn, sid, [
            product("p-draft2", tab="draft", name="甲二", stock_num=9),
        ], NOW)
    with engine.connect() as conn:
        rows, total = catalog_store.list_products(
            conn, [sid], quick="draft", keyword="甲", sort="stock_num", order="desc")
    assert total == 2 and _nos(rows, "product_id") == ["p-draft2", "p-draft"]


def test_product_status_sorts_by_display_order(engine):
    sid = _shop(engine)
    _products(engine, sid)
    with engine.connect() as conn:
        rows, _ = catalog_store.list_products(conn, [sid], sort="tab", order="asc")
        desc, _ = catalog_store.list_products(conn, [sid], sort="tab", order="desc")
    # 在售 → 草稿 → 未通过 → 禁售 / 下架，空值最后；中文文案与英文代码同名次（同名次按 id）
    assert _nos(rows, "product_id") == [
        "p-on", "p-sell", "p-draft", "p-unpass", "p-forbidden", "p-off", "p-none"]
    assert _nos(desc, "product_id") == [
        "p-off", "p-forbidden", "p-unpass", "p-draft", "p-sell", "p-on", "p-none"]


# ---- 库存 ----


def _stock(engine, sid):
    with engine.begin() as conn:
        catalog_store.upsert_stock(conn, sid, [
            stock("s-ok", total=5), stock("s-alarm", total=1, alarm=True),
            stock("s-out", total=0), stock("s-out-alarm", total=0, alarm=True),
        ], NOW)


def test_stock_quick_filters(engine):
    sid = _shop(engine)
    _stock(engine, sid)
    with engine.connect() as conn:
        alarm, _ = catalog_store.list_stock(conn, [sid], quick="alarm")
        out, _ = catalog_store.list_stock(conn, [sid], quick="sold_out")
    assert sorted(_nos(alarm, "product_id")) == ["s-alarm", "s-out-alarm"]
    assert sorted(_nos(out, "product_id")) == ["s-out", "s-out-alarm"]


def test_stock_status_sorts_by_badge_order(engine):
    sid = _shop(engine)
    _stock(engine, sid)
    with engine.connect() as conn:
        rows, _ = catalog_store.list_stock(conn, [sid], sort="status", order="asc")
    # 徽标：正常 → 预警（预警优先于售罄）→ 售罄
    assert _nos(rows, "product_id") == ["s-ok", "s-alarm", "s-out-alarm", "s-out"]


# ---- 售后 ----


def _with_text(dto, status_text=None, buttons=()):
    raw = {"after_sale_info": {"after_sale_id": dto.after_sale_id},
           "text_part": {"after_sale_status_text": status_text} if status_text else {},
           "buttons": [{"button": b} for b in buttons]}
    return replace(dto, raw=raw)


def test_aftersale_quick_filters(engine):
    sid = _shop(engine)
    with engine.begin() as conn:
        aftersale_store.upsert_aftersales(conn, sid, [
            _with_text(aftersale("audit", deadline="2026-11-30T00:00:00Z"),
                       buttons=("refund_audit", "handle")),
            _with_text(aftersale("due", deadline="2026-11-26T12:00:00Z"), buttons=("handle",)),
            _with_text(aftersale("over", deadline="2026-11-25T12:00:00Z")),
            _with_text(aftersale("done", deadline=None), buttons=("refund_audit",)),
        ], NOW)

    def q(quick):
        with engine.connect() as conn:
            rows, _ = aftersale_store.list_aftersales(
                conn, [sid], quick=quick, due_before=T_24H, by_deadline=True)
        return _nos(rows, "after_sale_id")

    assert q("pending") == ["over", "due", "audit"]
    assert q("audit") == ["audit"]
    assert q("due_soon") == ["over", "due"]


def test_aftersale_status_sorts_by_displayed_label(engine):
    sid = _shop(engine)
    with engine.begin() as conn:
        aftersale_store.upsert_aftersales(conn, sid, [
            _with_text(replace(aftersale("1"), status=30), "售后完成"),
            _with_text(replace(aftersale("2"), status=13), "待商家处理"),
            _with_text(replace(aftersale("3"), status=30), "售后完成"),
            _with_text(replace(aftersale("4"), status=7)),  # 无文案：显示「状态 7」
        ], NOW)
    with engine.connect() as conn:
        rows, _ = aftersale_store.list_aftersales(conn, [sid], sort="status", order="asc")
    labels = [
        json.loads(r["detail_json"])["text_part"].get("after_sale_status_text")
        or f"状态 {r['status']}"
        for r in rows
    ]
    assert labels == sorted(labels)  # 与显示文案同序，同名的挨在一起
    assert _nos(rows, "after_sale_id")[:2] == ["1", "3"]


# ---- 对账 ----


def test_finding_status_and_kind_sort_by_display_order(engine):
    from app.domain.reconcile_rules import Finding

    sid = _shop(engine)

    def f(kind):
        return Finding(kind, None, None, None, None, None, None, "")

    with engine.begin() as conn:
        reconcile_store.create_run(conn, "r1", [sid], 30, NOW)
        reconcile_store.insert_findings(conn, "r1", sid, [
            ("o1", f("waybill_mismatch")), ("o2", f("local_shipped_platform_not")),
            ("o3", f("platform_shipped_local_not")),
        ], NOW)
        first = reconcile_store.list_findings(conn, [sid], None, None, None, 1, 10)[0]
        reconcile_store.mark_finding(conn, first[-1]["id"], "handled", NOW)  # o1 已处理
    with engine.connect() as conn:
        by_status, _ = reconcile_store.list_findings(
            conn, [sid], None, None, None, 1, 10, sort="status", order="asc")
        by_kind, _ = reconcile_store.list_findings(
            conn, [sid], None, None, None, 1, 10, sort="kind", order="asc")
    # 字典序是 handled < open；界面是 未处理 → 已处理
    assert [r["status"] for r in by_status] == ["open", "open", "handled"]
    assert _nos(by_kind, "shop_order_id") == ["o2", "o3", "o1"]
