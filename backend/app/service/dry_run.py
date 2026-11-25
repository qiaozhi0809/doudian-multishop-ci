"""演练模式（overview 14.11 / engineering-rules 8.3）：只记录「将发出的请求」，不发真实写请求。

设计要点：
- 拦在 service 的写入口（取号 / 一体 / 作废 / 发货 / 打印），**不进入**状态机，
  避免把假的运单号 / 已发货状态写进本地库——否则关掉演练后幂等键会把真单当成已完成。
- 每条意图写一条 `audit_log`：action 以 `dry_run_` 开头，result 固定 `dry_run`。
- 只读请求（拉单、检查、探测）在演练模式下照常执行，便于用真实数据预览。
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import Engine

from app.domain.audit import CallRecord
from app.store import audit_store

ACTION_PREFIX = "dry_run_"
RESULT = "dry_run"
REASON = "演练模式：已记录请求，未发送"


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Intent:
    """一次「本应发出」的写请求。shop_id 为 None 表示跨店批次。"""

    action: str
    actor: str
    shop_id: int | None = None
    request: dict = field(default_factory=dict)
    response: dict = field(default_factory=dict)


def record(
    engine: Engine, intents: Sequence[Intent],
    clock: Callable[[], datetime] = utc_now,
) -> None:
    now = clock().strftime("%Y-%m-%dT%H:%M:%SZ")
    with engine.begin() as conn:
        for intent in intents:
            audit_store.insert(conn, CallRecord(
                shop_id=intent.shop_id,
                action=f"{ACTION_PREFIX}{intent.action}",
                actor=intent.actor,
                req_summary={"simulated": True, **intent.request},
                resp_summary=intent.response or {"simulated": True},
                result=RESULT,
            ), now)
