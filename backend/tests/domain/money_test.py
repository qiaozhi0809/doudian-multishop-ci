import pytest

from app.domain.money import cents_to_yuan_str, yuan_to_cents


def test_yuan_to_cents():
    assert yuan_to_cents("12.34") == 1234
    assert yuan_to_cents(5) == 500
    assert yuan_to_cents("0.1") == 10


def test_yuan_to_cents_rejects_sub_cent():
    with pytest.raises(ValueError):
        yuan_to_cents("0.001")


def test_cents_to_yuan_str():
    assert cents_to_yuan_str(1234) == "12.34"
    assert cents_to_yuan_str(5) == "0.05"
    assert cents_to_yuan_str(-250) == "-2.50"
