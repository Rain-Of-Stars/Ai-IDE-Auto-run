# -*- coding: utf-8 -*-
"""
应用共享状态中心：
- 统一维护“启用日志”状态，提供Qt信号用于跨模块实时同步；
- 集中处理文件日志启用与配置持久化，避免不同入口重复实现。

使用方式：
from auto_approve.app_state import get_app_state
state = get_app_state()
state.set_enable_logging(True)  # 将立即启用文件日志并保存到 config.json
state.loggingChanged.connect(slot)  # 订阅状态变化
"""
from __future__ import annotations

from PySide6 import QtCore

from auto_approve.config_manager import load_config, save_config
from auto_approve.logger_manager import enable_file_logging


class AppState(QtCore.QObject):
    """应用级共享状态对象（单例）。"""

    # 日志开关变化信号
    loggingChanged = QtCore.Signal(bool)

    def __init__(self):
        super().__init__()
        # 初始状态从配置读取，确保与磁盘一致
        try:
            cfg = load_config()
            self._enable_logging: bool = bool(getattr(cfg, "enable_logging", False))
            # 确保启动时文件日志状态与配置一致
            enable_file_logging(self._enable_logging)
        except Exception:
            self._enable_logging = False

    # 只读属性，便于外部快速读取当前状态
    @property
    def enable_logging(self) -> bool:
        return bool(self._enable_logging)

    def set_enable_logging(self, value: bool, *, persist: bool = True, emit_signal: bool = True) -> None:
        """设置“启用日志”状态。
        参数：
        - value: 目标布尔值
        - persist: 是否写入配置文件（默认True）
        - emit_signal: 是否发出变化信号（默认True）
        说明：
        - 无论是否持久化，都会立即调用 enable_file_logging 以使日志开关即时生效。
        - 若新旧状态一致且无需强制持久化/发信号，则仅确保 enable_file_logging 一致。
        """
        value = bool(value)
        changed = (value != self._enable_logging)
        self._enable_logging = value

        # 立即应用文件日志开关
        try:
            enable_file_logging(self._enable_logging)
        except Exception:
            pass

        # 可选持久化到配置
        if persist:
            try:
                cfg = load_config()
                cfg.enable_logging = self._enable_logging
                save_config(cfg)
            except Exception:
                pass

        # 仅在需要时发信号（避免不必要的环路）
        if emit_signal and changed:
            try:
                self.loggingChanged.emit(self._enable_logging)
            except Exception:
                pass


# 单例持有者
__app_state_singleton: AppState | None = None


def get_app_state() -> AppState:
    """获取全局共享状态单例。"""
    global __app_state_singleton
    if __app_state_singleton is None:
        __app_state_singleton = AppState()
    return __app_state_singleton
