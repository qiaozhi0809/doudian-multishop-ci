"""最长存活时间由各用途的最坏耗时推导，巡检不会关掉还在正常工作的浏览器。"""

from app.adapter.browser import browser_timing as t
from app.adapter.browser.browser_registry import MAX_AGE_S, Purpose
from app.service.shop_login import SCAN_TIMEOUT_S


def test_scrape_max_age_exceeds_worst_case_runtime():
    assert t.SCRAPE_WORST_S == 3 * (45 + 8) + 4
    assert MAX_AGE_S[Purpose.SCRAPE] >= t.SCRAPE_WORST_S + t.LAUNCH_MARGIN_S


def test_login_max_age_follows_scan_wait():
    assert SCAN_TIMEOUT_S == t.SCAN_WAIT_S
    assert MAX_AGE_S[Purpose.LOGIN] == t.login_max_age(SCAN_TIMEOUT_S) >= 600
    longer = 3600
    worst = t.LOGIN_NAV_TIMEOUT_S + longer + t.LOGIN_LOAD_WAIT_S
    assert t.login_max_age(longer) >= worst + t.LAUNCH_MARGIN_S
