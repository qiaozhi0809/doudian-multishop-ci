"""幂等键规则（backend 5.11）：取号按 seq 递增，作废按运单号。"""

from app.domain.idempotency import label_key, next_seq, void_key


def test_label_key_contains_shop_order_seq():
    assert label_key(3, "6900000000000000001", 2) == "label:3:6900000000000000001:2"


def test_label_key_changes_after_void():
    first = label_key(1, "o1", next_seq(0))
    second = label_key(1, "o1", next_seq(1))
    assert first != second


def test_void_key_uses_courier_and_waybill():
    assert void_key(2, "zhongtong", "79209902836406") == "void:2:zhongtong:79209902836406"


def test_next_seq_increments():
    assert next_seq(0) == 1
    assert next_seq(1) == 2
