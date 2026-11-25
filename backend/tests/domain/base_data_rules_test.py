from app.domain.base_data_rules import account_usable, compute_readiness


def test_account_usable():
    assert account_usable(5) is True
    assert account_usable(-1) is True  # 月结账户不计张数
    assert account_usable(0) is False
    assert account_usable(None) is False
    assert account_usable(-2) is False


def test_ready_with_one_complete_courier():
    ok, reasons = compute_readiness(True, {"jd", "sf"}, {"sf"})
    assert ok is True and reasons == []


def test_not_ready_without_default_address():
    ok, reasons = compute_readiness(False, {"jd"}, {"jd"})
    assert ok is False and reasons == ["没有默认发货地址"]


def test_not_ready_reasons_for_templates_and_accounts():
    assert compute_readiness(True, set(), {"jd"})[1] == ["没有面单模板"]
    assert compute_readiness(True, {"jd"}, set())[1] == ["没有可用面单账户（无账户或余额为 0）"]
    assert compute_readiness(True, {"jd"}, {"sf"})[1] == [
        "没有快递同时具备面单模板和可用面单账户"
    ]
    assert compute_readiness(False, set(), set())[1] == [
        "没有默认发货地址", "没有面单模板", "没有可用面单账户（无账户或余额为 0）"]
