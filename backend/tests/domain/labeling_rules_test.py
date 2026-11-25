"""取号前置规则（纯函数）：账户/快递选择、订单可取号判断、解密范围。"""

from app.domain.labeling_rules import (
    courier_options,
    decrypt_allowed,
    order_blockers,
    pick_courier,
    select_account,
)
from app.domain.order_status import LocalOrderStatus, PlatformOrderStatus

STOCK_UP = int(PlatformOrderStatus.STOCK_UP)
SHIPPED = int(PlatformOrderStatus.SHIPPED)


def _account(courier="zt", ebill="e1", net="n1", balance=10, is_default=False):
    return {"courier_code": courier, "ebill_id": ebill, "net_code": net,
            "balance": balance, "is_default": int(is_default)}


def _item(sku_order_id="so1", product_id="p1", sku_id: str | None = "s1"):
    return {"sku_order_id": sku_order_id, "product_id": product_id, "sku_id": sku_id}


# ---- 面单账户（DEC-05 建议稿） ----

def test_select_account_none_when_unusable():
    assert select_account([_account(balance=0)], "zt") is None
    assert select_account([], "zt") is None


def test_select_account_prefers_default():
    accounts = [
        _account("zt", ebill="a", balance=100),
        _account("zt", ebill="b", balance=1, is_default=True),
    ]
    assert select_account(accounts, "zt")["ebill_id"] == "b"


def test_select_account_max_balance_without_default():
    accounts = [_account("zt", ebill="a", balance=5), _account("zt", ebill="b", balance=9)]
    assert select_account(accounts, "zt")["ebill_id"] == "b"


def test_select_account_monthly_ranked_highest():
    accounts = [
        _account("zt", ebill="prepaid", balance=100),
        _account("zt", ebill="monthly", balance=-1),
    ]
    assert select_account(accounts, "zt")["ebill_id"] == "monthly"


def test_select_account_ignores_other_couriers():
    assert select_account([_account("jd")], "zt") is None


# ---- 快递选择 ----

def test_courier_options_need_template_and_usable_account():
    templates = [{"courier_code": "zt"}, {"courier_code": "jd"}, {"courier_code": None}]
    accounts = [_account("zt", balance=3), _account("jd", balance=0)]
    assert courier_options(templates, accounts) == ["zt"]


def test_pick_courier_prefers_valid_preference():
    templates = [{"courier_code": "zt"}, {"courier_code": "jd"}]
    accounts = [_account("zt"), _account("jd")]
    assert pick_courier(templates, accounts, "jd") == "jd"
    assert pick_courier(templates, accounts, "yunda") == "jd"
    assert pick_courier([], [], "zt") is None


# ---- 订单可否取号 ----

def test_order_ready_no_blockers():
    pending = LocalOrderStatus.PENDING_LABEL.value
    assert order_blockers(STOCK_UP, "c1", [_item()], False, pending) == []


def test_blockers_platform_not_stock_up():
    pending = LocalOrderStatus.PENDING_LABEL.value
    assert any("待发货" in r for r in
               order_blockers(SHIPPED, "c1", [_item()], False, pending))


def test_blockers_local_status_not_labelable():
    reasons = order_blockers(STOCK_UP, "c1", [_item()], False, LocalOrderStatus.SHIPPED.value)
    assert any("状态" in r for r in reasons)


def test_blockers_missing_combine_id():
    assert any("combine_id" in r for r in
               order_blockers(STOCK_UP, None, [_item()], False, LocalOrderStatus.SYNCED.value))


def test_blockers_missing_item_fields():
    reasons = order_blockers(
        STOCK_UP, "c1", [_item(sku_id=None)], False, LocalOrderStatus.SYNCED.value)
    assert any("sku_id" in r for r in reasons)
    assert any("商品行" in r for r in
               order_blockers(STOCK_UP, "c1", [], False, LocalOrderStatus.SYNCED.value))


def test_blockers_active_waybill():
    pending = LocalOrderStatus.PENDING_LABEL.value
    assert any("面单" in r for r in
               order_blockers(STOCK_UP, "c1", [_item()], True, pending))


# ---- 解密范围（flows 7.3 约束 1） ----

def test_decrypt_allowed_pending_chain():
    assert decrypt_allowed(LocalOrderStatus.LABEL_OBTAINED.value, STOCK_UP)
    assert decrypt_allowed(LocalOrderStatus.PENDING_LABEL.value, STOCK_UP)


def test_decrypt_denied_after_ship_or_cancel():
    for status in (LocalOrderStatus.SHIPPED, LocalOrderStatus.CLOSED, LocalOrderStatus.CANCELLED):
        assert not decrypt_allowed(status.value, SHIPPED)
    assert not decrypt_allowed(LocalOrderStatus.SHIPPED.value, STOCK_UP)
