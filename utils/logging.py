"""Iris AI Gateway - 日志配置"""

import logging
import sys
import os
from datetime import datetime
from typing import Optional


def setup_logging(level: str = "info", log_format: Optional[str] = None):
    """配置日志系统

    - 控制台：只输出 WARNING 及以上（避免 API 调用时刷屏）
    - 文件：输出 INFO 及以上，按日期轮转
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    if log_format is None:
        log_format = (
            "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
        )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []

    # 1. 控制台 Handler — 只显示 WARNING 及以上，避免刷屏
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter(log_format))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    root_logger.addHandler(console_handler)

    # 2. 文件 Handler — 保存 INFO 及以上完整日志
    log_dir = "./data/logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"iris_{datetime.now().strftime('%Y%m%d')}.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)

    # 设置特定模块的日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
