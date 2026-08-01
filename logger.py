"""
日志模块 — 统一日志管理，支持文件和控制台输出。
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

LOG_DIR = Path(__file__).parent / "logs"
LOG_FILE = LOG_DIR / "news_daily.log"
MAX_BYTES = 5 * 1024 * 1024  # 5MB
BACKUP_COUNT = 3

_logger: Optional[logging.Logger] = None


def _ensure_log_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)


def setup_logger(level: int = logging.INFO) -> logging.Logger:
    """初始化并返回全局 logger，同时输出到文件和控制台。"""
    global _logger

    if _logger is not None:
        return _logger

    _ensure_log_dir()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    _logger = logging.getLogger("NewsDaily")
    _logger.setLevel(level)
    _logger.addHandler(file_handler)
    _logger.addHandler(console_handler)

    return _logger


def get_logger() -> logging.Logger:
    """获取已初始化的 logger，若未初始化则自动创建。"""
    global _logger
    if _logger is None:
        return setup_logger()
    return _logger
