from app.domain.order_status import (
    PLATFORM_FINAL_STATUSES,
    LocalOrderStatus,
    OrderTab,
    PlatformOrderStatus,
)


def test_platform_status_known():
    assert PlatformOrderStatus(4) is PlatformOrderStatus.CLOSED
    assert PlatformOrderStatus(3) is PlatformOrderStatus.SHIPPED
    assert PlatformOrderStatus(5) is PlatformOrderStatus.COMPLETED


def test_platform_status_unknown():
    # 未知值不在枚举中，调用方保留原始整数
    assert 2 not in {s.value for s in PlatformOrderStatus}
    assert PLATFORM_FINAL_STATUSES == frozenset({3, 4, 5})


def test_tabs_and_local_status_are_separate_str_enums():
    assert OrderTab.STOCK_UP == "stock_up"
    assert {t.value for t in OrderTab} == {
        "all", "unpaid", "stock_up", "on_delivery", "received", "closed",
    }
    assert {s.value for s in LocalOrderStatus} == {
        "synced", "pending_label", "label_obtained", "printed",
        "shipped", "closed", "exception", "cancelled",
    }
