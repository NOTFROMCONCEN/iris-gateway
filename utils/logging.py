"""Iris AI Gateway - 日志配置"""

import logging
import sys
from typing import Optional


def setup_logging(level: str = "info", log_format: Optional[str] = None):
    """配置日志系统"""
    log_level = getattr(logging, level.upper(), logging.INFO)

    if log_format is None:
        log_format = (
            "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(logging.Formatter(log_format))

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []
    root_logger.addHandler(handler)

    # 设置特定模块的日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
