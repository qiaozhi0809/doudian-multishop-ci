"""审计记录（adapter 产出，store 落库）。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CallRecord:
    shop_id: int | None
    action: str
    actor: str
    req_summary: dict = field(default_factory=dict)
    resp_summary: dict = field(default_factory=dict)
    result: str = ""
    duration_ms: int = 0
