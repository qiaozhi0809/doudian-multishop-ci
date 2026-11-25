"""售后状态与待办口径（docs/api/aftersale.md 附录 E）。

平台未公开 `after_sale_status` / `after_sale_type` 的数字取值，因此**不猜测数字映射**：
本地只保留原始整数，展示文案取平台下发的 `text_part`（E.6 第 3 条）。
待办量按平台 `counts` 接口的分组计数计算（E.2），不依赖数字枚举。
"""

from collections.abc import Mapping

# 分组只取「组级」字段，避免与组内细分字段重复相加（E.2：all_audit 已包含各类待审）
AUDIT_FIELDS = ("all_audit",)
RECEIVE_FIELDS = ("return_for_receive", "exchange_for_receive")
ARBITRATE_FIELDS = ("arbitrate_pending",)
PENDING_FIELDS = AUDIT_FIELDS + RECEIVE_FIELDS + ARBITRATE_FIELDS

# 时效预警：临近超时 / 催审 / 一天内到期
ALERT_FIELDS = ("urge_audit", "approaching_deadline_audit", "audit_ddl_in_one_day")

WAIT_FIELDS = ("wait_user_delivery", "wait_user_sign", "all_wait_user_sign")
RISK_FIELDS = ("logistics_abnormal", "suspected_violation", "appeal_todo")

# 向平台显式声明的查询字段（E.2：不传可能返回全量或报错）
COUNT_FIELDS: tuple[str, ...] = PENDING_FIELDS + ALERT_FIELDS + WAIT_FIELDS + RISK_FIELDS + (
    "refund_audit", "return_audit", "exchange_audit", "resend_audit", "repair_audit",
)

# 界面分组：顺序即展示顺序
COUNT_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("audit", "待审核", ("all_audit", "refund_audit", "return_audit",
                         "exchange_audit", "resend_audit", "repair_audit")),
    ("receive", "待收货 / 待发货", RECEIVE_FIELDS + WAIT_FIELDS),
    ("arbitrate", "仲裁", ARBITRATE_FIELDS + ("arbitrate_pending_negotiation",
                                               "arbitrate_pending_evidence")),
    ("alert", "时效预警", ALERT_FIELDS),
    ("risk", "风险与异常", RISK_FIELDS),
)


def counts_fields_param() -> str:
    """`counts` 接口的 `fields` 参数值。"""
    return ",".join(COUNT_FIELDS)


def pending_total(counts: Mapping[str, int]) -> int:
    """需商家处理的售后量（backend 5.10 统计算法）。"""
    return sum(int(counts.get(f, 0)) for f in PENDING_FIELDS)


def is_open(deadline_iso: str | None) -> bool:
    """有处理截止时间 = 平台侧仍在流转；已完结的售后该字段为 0（解析后为 None）。"""
    return deadline_iso is not None
