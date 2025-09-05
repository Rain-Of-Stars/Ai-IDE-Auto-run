# -*- coding: utf-8 -*-
"""
自动窗口句柄更新模块
根据配置的进程名称自动查找并更新目标窗口HWND
"""
from __future__ import annotations
import threading
import time
from typing import Optional, Callable

from PySide6 import QtCore

from capture.monitor_utils import find_window_by_process
from auto_approve.logger_manager import get_logger
from auto_approve.config_manager import AppConfig


class AutoHWNDUpdater(QtCore.QObject):
    """自动窗口句柄更新器"""
    
    # 信号：HWND更新完成
    hwnd_updated = QtCore.Signal(int, str)  # hwnd, process_name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        self._config: Optional[AppConfig] = None
        self._update_timer: Optional[threading.Timer] = None
        self._running = False
        self._lock = threading.Lock()
        self._current_hwnd = 0
        self._update_callback: Optional[Callable[[int], None]] = None
        
    def set_config(self, config: AppConfig):
        """设置配置"""
        with self._lock:
            self._config = config
            self._restart_if_needed()
            
    def set_update_callback(self, callback: Optional[Callable[[int], None]]):
        """设置HWND更新回调函数"""
        self._update_callback = callback
        
    def start(self):
        """启动自动更新"""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._schedule_next_update()
            self.logger.info("自动窗口句柄更新器已启动")
            
    def stop(self):
        """停止自动更新"""
        with self._lock:
            self._running = False
            if self._update_timer:
                self._update_timer.cancel()
                self._update_timer = None
            self.logger.info("自动窗口句柄更新器已停止")
            
    def _restart_if_needed(self):
        """根据配置重启更新器"""
        if self._config and self._config.auto_update_hwnd_by_process and self._running:
            # 取消当前定时器
            if self._update_timer:
                self._update_timer.cancel()
                self._update_timer = None
            # 立即执行一次更新
            self._perform_update()
            # 重新调度
            self._schedule_next_update()
        elif self._running and (not self._config or not self._config.auto_update_hwnd_by_process):
            # 如果配置禁用，停止更新
            self.stop()
            
    def _schedule_next_update(self):
        """调度下一次更新"""
        with self._lock:
            if not self._running or not self._config:
                return
                
            if not self._config.auto_update_hwnd_by_process:
                return
                
            interval_ms = max(1000, self._config.auto_update_hwnd_interval_ms)
            self._update_timer = threading.Timer(interval_ms / 1000.0, self._perform_update)
            self._update_timer.start()
            
    def _perform_update(self):
        """执行HWND更新"""
        try:
            with self._lock:
                if not self._running or not self._config:
                    return
                    
                if not self._config.auto_update_hwnd_by_process:
                    return
                    
                process_name = self._config.target_process
                if not process_name:
                    self.logger.warning("自动更新HWND失败：未配置目标进程名称")
                    return
                    
                partial_match = self._config.process_partial_match
                
            # 在锁外执行查找操作，避免阻塞
            new_hwnd = find_window_by_process(process_name, partial_match)
            
            with self._lock:
                if new_hwnd and new_hwnd != self._current_hwnd:
                    self._current_hwnd = new_hwnd
                    self.logger.info(f"自动更新HWND：进程'{process_name}' -> HWND={new_hwnd}")
                    
                    # 发出信号
                    self.hwnd_updated.emit(new_hwnd, process_name)
                    
                    # 调用回调函数
                    if self._update_callback:
                        try:
                            self._update_callback(new_hwnd)
                        except Exception as e:
                            self.logger.error(f"HWND更新回调失败: {e}")
                            
                elif not new_hwnd:
                    self.logger.debug(f"自动更新HWND：未找到进程'{process_name}'的窗口")
                    
        except Exception as e:
            self.logger.error(f"自动更新HWND失败: {e}")
        finally:
            # 调度下一次更新
            self._schedule_next_update()
            
    def get_current_hwnd(self) -> int:
        """获取当前HWND"""
        with self._lock:
            return self._current_hwnd
            
    def is_running(self) -> bool:
        """检查是否正在运行"""
        with self._lock:
            return self._running