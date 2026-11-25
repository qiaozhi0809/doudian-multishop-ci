"""任务状态与类型（data-model 6.2 ⑥）。状态流转由 service 推进，store 只读写。"""

from enum import StrEnum


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    VERIFYING = "verifying"  # 结果不明，待核实（backend 5.12）
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(StrEnum):
    OBTAIN_LABEL = "obtain_label"
    FETCH_AND_SHIP = "fetch_and_ship"
    VOID_LABEL = "void_label"
    RECOVER_LABEL = "recover_label"
    SHIP = "ship"
