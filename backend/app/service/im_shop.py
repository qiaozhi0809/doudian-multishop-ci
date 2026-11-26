"""飞鸽常驻页按店持有的状态：对外的接收状态，以及生命周期用的任务、锁与重试节奏。"""

import asyncio
from dataclasses import dataclass

from app.domain.im_rules import ImState
from app.service.im_retry import ShopRetry
from app.service.im_run import Run


@dataclass
class ImStatus:
    shop_id: int
    state: ImState
    since: str
    next_retry_at: str | None = None
    last_error: str | None = None


class ShopSlot:
    def __init__(self, status: ImStatus) -> None:
        self.status = status
        self.retry = ShopRetry()
        self.lock = asyncio.Lock()  # start / stop / restart / reconcile 逐个执行
        self.task: asyncio.Task | None = None  # 接收中、启动中或在等下次重试
        self.run: Run | None = None

    @property
    def id(self) -> int:
        return self.status.shop_id
