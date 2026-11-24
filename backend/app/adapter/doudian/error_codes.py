"""平台错误码（比较前一律转字符串）。"""

SUCCESS_CODES: frozenset[str] = frozenset({"0", "100000"})
SESSION_EXPIRED = "10008"
RISK_CODES: frozenset[str] = frozenset({"10001010A", "602502151"})
