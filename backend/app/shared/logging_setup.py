"""structlog 配置：所有日志事件先经 redact_mapping。"""

import logging
import sys

import structlog

from app.shared.redact import redact_mapping


def _redact_processor(_logger, _method, event_dict: dict) -> dict:
    return redact_mapping(event_dict)


class _StdoutLogger:
    """每次输出时才取 sys.stdout，避免持有已关闭的流（测试捕获、重定向）。"""

    def msg(self, message: str) -> None:
        print(message, file=sys.stdout, flush=True)

    log = debug = info = warn = warning = error = critical = fatal = failure = exception = msg


def configure_logging(json: bool = True) -> None:
    renderer = structlog.processors.JSONRenderer(ensure_ascii=False) if json else (
        structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_processor,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=_StdoutLogger,
        cache_logger_on_first_use=False,
    )
