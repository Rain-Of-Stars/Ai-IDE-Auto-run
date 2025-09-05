# -*- coding: utf-8 -*-
"""
Windows Graphics Capture (WGC) 统一捕获包

本包提供基于 Windows Graphics Capture API 的统一窗口和显示器捕获功能，
完全替代传统的 mss 屏幕截取和 PrintWindow 回退方案。

主要特性：
- 纯 WGC 实现，支持硬件加速应用的稳定捕获
- 正确处理 RowPitch/Stride，避免图像变形
- Per Monitor V2 DPI 感知
- 高性能帧率控制和缓冲管理
- 统一的窗口/显示器枚举接口

核心类：
- WGCCaptureSession: WGC 捕获会话
- CaptureManager: 统一捕获管理器
- MonitorUtils: 显示器枚举工具
"""

from .wgc_backend import WGCCaptureSession
from .capture_manager import CaptureManager
from .monitor_utils import enum_windows, get_monitor_handles, get_primary_monitor, get_all_monitors_info
from .shared_frame_cache import get_shared_frame_cache, cleanup_shared_frame_cache
from .cache_manager import get_global_cache_manager, cleanup_global_cache_manager

__all__ = [
    'WGCCaptureSession',
    'CaptureManager',
    'enum_windows',
    'get_monitor_handles',
    'get_primary_monitor',
    'get_all_monitors_info',
    'get_shared_frame_cache',
    'cleanup_shared_frame_cache',
    'get_global_cache_manager',
    'cleanup_global_cache_manager'
]

__version__ = '1.0.0'
