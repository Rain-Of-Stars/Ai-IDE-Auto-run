# -*- coding: utf-8 -*-
"""
日志管理模块：按配置开关将日志输出到 log.txt，格式包含时间戳。
提供动态开启/关闭文件日志的能力。
"""
import logging
import os
from typing import Optional

_LOGGER_NAME = "auto_approver"
_LOG_FILE = "log.txt"

_logger = logging.getLogger(_LOGGER_NAME)
_logger.setLevel(logging.INFO)

# 控制台仅在调试时使用，这里默认关闭以减少干扰
if not _logger.handlers:
    _logger.addHandler(logging.NullHandler())

_file_handler: Optional[logging.Handler] = None


def _make_formatter() -> logging.Formatter:
    # 时间、级别、信息
    return logging.Formatter(fmt="%(asctime)s | %(levelname)s | %(message)s",
                             datefmt="%Y-%m-%d %H:%M:%S")


def enable_file_logging(enable: bool, log_path: Optional[str] = None) -> None:
    """根据 enable 开关文件日志输出。"""
    global _file_handler
    if enable:
        if _file_handler is None:
            path = os.path.abspath(log_path or _LOG_FILE)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            handler = logging.FileHandler(path, mode="a", encoding="utf-8")
            handler.setFormatter(_make_formatter())
            _logger.addHandler(handler)
            _file_handler = handler
        _logger.info("文件日志已开启")
    else:
        if _file_handler is not None:
            _logger.removeHandler(_file_handler)
            try:
                _file_handler.close()
            except Exception:
                pass
            _file_handler = None
        _logger.info("文件日志已关闭")


def get_logger() -> logging.Logger:
    return _logger
