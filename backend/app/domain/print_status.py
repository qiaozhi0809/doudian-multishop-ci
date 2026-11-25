"""打印任务状态与结果码（data-model 6.2 ⑤-b）。状态流转由 service 推进，store 只读写。"""

from enum import StrEnum


class PrintJobStatus(StrEnum):
    QUEUED = "queued"
    SUCCESS = "success"
    FAILED = "failed"


# 失败结果码（print_job.result_code），服务层与界面共用
RESULT_NO_PRINT_DATA = "no_print_data"  # 平台没给打印数据：只能手动补打（P3）
RESULT_COMPONENT_FAILED = "component_failed"  # 组件回执失败（已重试一次）
RESULT_COMPONENT_UNAVAILABLE = "component_unavailable"  # 组件未启动 / 连不上
RESULT_TIMEOUT = "no_response"  # 等回执超时
RESULT_UNRECOGNIZED = "unrecognized_result"  # 回执无法判断成败
RESULT_NO_PRINTER = "no_printer"  # 没有可用打印机
