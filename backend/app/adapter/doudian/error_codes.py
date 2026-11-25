"""平台错误码（比较前一律转字符串）。"""

SUCCESS_CODES: frozenset[str] = frozenset({"0", "100000"})
SESSION_EXPIRED = "10008"
DECRYPT_RATE_RISK = "602502151"  # 地址解密过快触发；只暂停该店解密，不暂停取号（flows 7.3）
RISK_CODES: frozenset[str] = frozenset({"10001010A", DECRYPT_RATE_RISK})
