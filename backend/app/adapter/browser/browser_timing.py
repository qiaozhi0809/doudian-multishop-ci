"""浏览器各用途的耗时上限与最长存活时间：后者由前者推导，二者不会各改各的。"""

SCAN_WAIT_S = 300  # 扫码登录等待人工扫码
LOGIN_NAV_TIMEOUT_S = 30  # 打开订单页（Playwright 默认导航超时）
LOGIN_LOAD_WAIT_S = 10  # 拿到 token 后等页面加载完

SCRAPE_PAGES = 3
SCRAPE_GOTO_TIMEOUT_S = 45
SCRAPE_RENDER_WAIT_S = 8
SCRAPE_TAB_WAIT_S = 4  # 资质页点「主体信息」后再等

LAUNCH_MARGIN_S = 120  # 冷启动（Windows 首次 10–20 秒）、关闭与巡检错位的余量

LOGIN_DEFAULT_MAX_S = 10 * 60
SCRAPE_DEFAULT_MAX_S = 2 * 60
IM_MAX_S = 24 * 3600  # 常驻，到期关闭由持有方重开，即每天重启一次

SCRAPE_WORST_S = (
    SCRAPE_PAGES * (SCRAPE_GOTO_TIMEOUT_S + SCRAPE_RENDER_WAIT_S) + SCRAPE_TAB_WAIT_S
)


def login_max_age(wait_s: float = SCAN_WAIT_S) -> float:
    """扫码浏览器的最长存活：不短于 10 分钟，也一定长于本次扫码的最坏耗时加余量。"""
    worst = LOGIN_NAV_TIMEOUT_S + wait_s + LOGIN_LOAD_WAIT_S
    return max(LOGIN_DEFAULT_MAX_S, worst + LAUNCH_MARGIN_S)


SCRAPE_MAX_S = max(SCRAPE_DEFAULT_MAX_S, SCRAPE_WORST_S + LAUNCH_MARGIN_S)
