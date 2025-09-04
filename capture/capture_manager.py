# -*- coding: utf-8 -*-
"""
统一捕获管理器

提供高级的窗口和显示器捕获接口，封装 WGC 会话管理、
最小化窗口处理、异常恢复等功能。
"""

from __future__ import annotations
import ctypes
import time
from typing import Optional, Union, Tuple
import numpy as np

# Windows API
from ctypes import wintypes
user32 = ctypes.windll.user32

# 内部模块
from .wgc_backend import WGCCaptureSession, WGC_AVAILABLE
from .monitor_utils import enum_windows, get_monitor_handles, find_window_by_title, find_window_by_process
from auto_approve.logger_manager import get_logger

# Windows API 常量
SW_SHOWNOACTIVATE = 4
SW_MINIMIZE = 6
SWP_NOACTIVATE = 0x0010
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004


class CaptureManager:
    """
    统一捕获管理器
    
    提供简化的窗口/显示器捕获接口，自动处理：
    - 窗口查找和验证
    - 最小化窗口的无感恢复
    - WGC 会话生命周期管理
    - 异常处理和重试机制
    """
    
    def __init__(self):
        self._logger = get_logger()
        self._session: Optional[WGCCaptureSession] = None
        self._target_hwnd: Optional[int] = None
        self._target_hmonitor: Optional[int] = None
        self._was_minimized = False
        self._restore_minimized = True
        
        # 性能配置
        self._target_fps = 30
        self._include_cursor = False
        self._border_required = False
        
        if not WGC_AVAILABLE:
            self._logger.error("Windows Graphics Capture 不可用")
            raise RuntimeError("WGC 库未安装或不兼容")
            
    def open_window(self, target: Union[str, int], partial_match: bool = True) -> bool:
        """
        打开窗口捕获
        
        Args:
            target: 窗口标题(str)、进程名(str)或窗口句柄(int)
            partial_match: 字符串匹配时是否允许部分匹配
            
        Returns:
            bool: 是否成功打开
        """
        try:
            # 解析目标
            hwnd = self._resolve_window_target(target, partial_match)
            if not hwnd:
                self._logger.error(f"无法找到目标窗口: {target}")
                return False
                
            # 验证窗口
            if not user32.IsWindow(hwnd):
                self._logger.error(f"无效的窗口句柄: {hwnd}")
                return False
                
            # 关闭现有会话
            self.close()
            
            # 创建新会话
            self._session = WGCCaptureSession.from_hwnd(hwnd)
            self._target_hwnd = hwnd
            
            # 启动捕获
            success = self._session.start(
                target_fps=self._target_fps,
                include_cursor=self._include_cursor,
                border_required=self._border_required
            )
            
            if success:
                self._logger.info(f"窗口捕获已启动: hwnd={hwnd}, title='{self._get_window_title(hwnd)}'")
            else:
                self._logger.error(f"窗口捕获启动失败: hwnd={hwnd}")
                self._session = None
                self._target_hwnd = None
                
            return success
            
        except Exception as e:
            self._logger.error(f"打开窗口捕获失败: {e}")
            return False
            
    def open_monitor(self, target: Union[int, str]) -> bool:
        """
        打开显示器捕获
        
        Args:
            target: 显示器索引(int)或显示器句柄(int)
            
        Returns:
            bool: 是否成功打开
        """
        try:
            # 解析显示器目标
            hmonitor = self._resolve_monitor_target(target)
            if not hmonitor:
                # 获取显示器信息用于错误提示
                from .monitor_utils import get_all_monitors_info
                monitors_info = get_all_monitors_info()
                self._logger.error(f"无法找到目标显示器: {target}")
                self._logger.error(f"当前系统有 {len(monitors_info)} 个显示器，有效索引: 0-{len(monitors_info)-1}")
                return False
                
            # 关闭现有会话
            self.close()
            
            # 创建新会话
            self._session = WGCCaptureSession.from_monitor(hmonitor)
            self._target_hmonitor = hmonitor
            
            # 启动捕获
            success = self._session.start(
                target_fps=self._target_fps,
                include_cursor=self._include_cursor,
                border_required=self._border_required
            )
            
            if success:
                self._logger.info(f"显示器捕获已启动: hmonitor={hmonitor}")
            else:
                self._logger.error(f"显示器捕获启动失败: hmonitor={hmonitor}")
                self._session = None
                self._target_hmonitor = None
                
            return success
            
        except Exception as e:
            self._logger.error(f"打开显示器捕获失败: {e}")
            return False
            
    def capture_frame(self, restore_after_capture: bool = False) -> Optional[np.ndarray]:
        """
        捕获一帧图像
        
        Args:
            restore_after_capture: 捕获后是否恢复窗口最小化状态
            
        Returns:
            np.ndarray: BGR 图像，失败返回 None
        """
        if not self._session:
            self._logger.error("捕获会话未初始化")
            return None
            
        try:
            # 处理最小化窗口
            if self._target_hwnd and self._restore_minimized:
                self._handle_minimized_window()
                
            # 捕获帧
            frame = self._session.grab()
            
            # 恢复最小化状态
            if restore_after_capture and self._was_minimized:
                self._restore_window_state()
                
            return frame
            
        except Exception as e:
            self._logger.error(f"捕获帧失败: {e}")
            return None
            
    def wait_for_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """等待新帧"""
        if not self._session:
            return None
        return self._session.wait_for_frame(timeout)
        
    def configure(self, fps: int = 30, include_cursor: bool = False, 
                  border_required: bool = False, restore_minimized: bool = True):
        """
        配置捕获参数
        
        Args:
            fps: 目标帧率
            include_cursor: 是否包含鼠标光标
            border_required: 是否需要窗口边框
            restore_minimized: 是否自动恢复最小化窗口
        """
        self._target_fps = max(1, min(fps, 60))
        self._include_cursor = include_cursor
        self._border_required = border_required
        self._restore_minimized = restore_minimized
        
        # 如果会话已启动，需要重启以应用新配置
        if self._session:
            if self._target_hwnd:
                hwnd = self._target_hwnd
                self.close()
                self.open_window(hwnd)
            elif self._target_hmonitor:
                hmonitor = self._target_hmonitor
                self.close()
                self.open_monitor(hmonitor)
                
    def get_stats(self) -> dict:
        """获取捕获统计信息"""
        if self._session:
            stats = self._session.get_stats()
            stats.update({
                'target_hwnd': self._target_hwnd,
                'target_hmonitor': self._target_hmonitor,
                'was_minimized': self._was_minimized
            })
            return stats
        return {}
        
    def close(self):
        """关闭捕获会话"""
        if self._session:
            self._session.close()
            self._session = None
            
        # 恢复窗口状态
        if self._was_minimized and self._target_hwnd:
            self._restore_window_state()
            
        self._target_hwnd = None
        self._target_hmonitor = None
        self._was_minimized = False
        
    def _resolve_window_target(self, target: Union[str, int], partial_match: bool) -> Optional[int]:
        """解析窗口目标为 HWND"""
        if isinstance(target, int):
            return target
            
        if isinstance(target, str):
            # 先尝试按标题查找
            hwnd = find_window_by_title(target, partial_match)
            if hwnd:
                return hwnd
                
            # 再尝试按进程名查找
            hwnd = find_window_by_process(target, partial_match)
            if hwnd:
                return hwnd
                
        return None
        
    def _resolve_monitor_target(self, target: Union[int, str]) -> Optional[int]:
        """解析显示器目标为 HMONITOR"""
        if isinstance(target, int):
            # 如果是小整数，当作索引处理
            if target < 100:
                monitors = get_monitor_handles()
                if 0 <= target < len(monitors):
                    return monitors[target]
                else:
                    # 提供详细的错误信息
                    self._logger.error(f"显示器索引 {target} 无效。当前系统有 {len(monitors)} 个显示器，有效索引范围: 0-{len(monitors)-1}")
                    if len(monitors) > 0:
                        self._logger.info(f"建议使用索引 0 (主显示器)")
                    return None
            else:
                # 大整数当作句柄处理
                return target

        return None
        
    def _handle_minimized_window(self):
        """处理最小化窗口"""
        if not self._target_hwnd:
            return
            
        try:
            # 检查是否最小化
            if user32.IsIconic(self._target_hwnd):
                if not self._was_minimized:
                    self._was_minimized = True
                    self._logger.debug(f"检测到最小化窗口: {self._target_hwnd}")
                    
                # 无感恢复（不激活）
                user32.ShowWindow(self._target_hwnd, SW_SHOWNOACTIVATE)
                
        except Exception as e:
            self._logger.warning(f"处理最小化窗口失败: {e}")
            
    def _restore_window_state(self):
        """恢复窗口最小化状态"""
        if self._was_minimized and self._target_hwnd:
            try:
                user32.ShowWindow(self._target_hwnd, SW_MINIMIZE)
                self._was_minimized = False
                self._logger.debug(f"已恢复窗口最小化状态: {self._target_hwnd}")
            except Exception as e:
                self._logger.warning(f"恢复窗口状态失败: {e}")
                
    def _get_window_title(self, hwnd: int) -> str:
        """获取窗口标题"""
        try:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                return buf.value
        except Exception:
            pass
        return ""
        
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def __del__(self):
        self.close()
