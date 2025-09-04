# -*- coding: utf-8 -*-
"""
Windows DPI 感知和坐标转换工具

提供 Per Monitor V2 DPI 感知设置和像素坐标与 DIP (Device Independent Pixels) 
之间的转换功能，确保在不同 DPI 缩放下的坐标一致性。
"""

from __future__ import annotations
import ctypes
from typing import Tuple, Optional
from ctypes import wintypes

# Windows API
user32 = ctypes.windll.user32
shcore = ctypes.windll.shcore
kernel32 = ctypes.windll.kernel32

from auto_approve.logger_manager import get_logger

# DPI 感知级别常量
DPI_AWARENESS_INVALID = -1
DPI_AWARENESS_UNAWARE = 0
DPI_AWARENESS_SYSTEM_AWARE = 1
DPI_AWARENESS_PER_MONITOR_AWARE = 2

# Process DPI Awareness Context 常量
DPI_AWARENESS_CONTEXT_UNAWARE = -1
DPI_AWARENESS_CONTEXT_SYSTEM_AWARE = -2
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE = -3
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
DPI_AWARENESS_CONTEXT_UNAWARE_GDISCALED = -5

# Monitor DPI Type
MDT_EFFECTIVE_DPI = 0
MDT_ANGULAR_DPI = 1
MDT_RAW_DPI = 2

# 标准 DPI 值
STANDARD_DPI = 96


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]


def set_process_dpi_awareness() -> bool:
    """
    设置进程为 Per Monitor V2 DPI 感知
    
    应在程序启动早期调用，最好在导入 Qt 之前。
    
    Returns:
        bool: 设置是否成功
    """
    logger = get_logger()
    
    try:
        # 尝试设置 Per Monitor V2 (Windows 10 1703+)
        if hasattr(user32, 'SetProcessDpiAwarenessContext'):
            result = user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
            if result:
                logger.info("已设置 Per Monitor V2 DPI 感知")
                return True
            else:
                logger.warning("Per Monitor V2 DPI 感知设置失败，尝试 Per Monitor V1")
                
        # 回退到 Per Monitor V1 (Windows 8.1+)
        if hasattr(shcore, 'SetProcessDpiAwareness'):
            try:
                shcore.SetProcessDpiAwareness(DPI_AWARENESS_PER_MONITOR_AWARE)
                logger.info("已设置 Per Monitor V1 DPI 感知")
                return True
            except OSError as e:
                if e.winerror == -2147024891:  # E_ACCESSDENIED
                    logger.info("DPI 感知已被设置（可能由其他组件设置）")
                    return True
                logger.warning(f"Per Monitor V1 DPI 感知设置失败: {e}")
                
        # 最后回退到系统 DPI 感知
        if hasattr(user32, 'SetProcessDPIAware'):
            result = user32.SetProcessDPIAware()
            if result:
                logger.info("已设置系统 DPI 感知")
                return True
            else:
                logger.warning("系统 DPI 感知设置失败")
                
    except Exception as e:
        logger.error(f"DPI 感知设置异常: {e}")
        
    logger.warning("所有 DPI 感知设置方法都失败，将使用默认设置")
    return False


def get_dpi_for_window(hwnd: int) -> Tuple[int, int]:
    """
    获取窗口的 DPI 值
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        Tuple[int, int]: (dpi_x, dpi_y)，失败返回 (96, 96)
    """
    try:
        # Windows 10 1607+ 方法
        if hasattr(user32, 'GetDpiForWindow'):
            dpi = user32.GetDpiForWindow(hwnd)
            if dpi > 0:
                return (dpi, dpi)
                
        # Windows 8.1+ 方法
        if hasattr(shcore, 'GetDpiForMonitor'):
            hmonitor = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
            if hmonitor:
                dpi_x = wintypes.UINT()
                dpi_y = wintypes.UINT()
                if shcore.GetDpiForMonitor(hmonitor, MDT_EFFECTIVE_DPI, 
                                         ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
                    return (dpi_x.value, dpi_y.value)
                    
        # 回退到系统 DPI
        hdc = user32.GetDC(hwnd)
        if hdc:
            try:
                dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                dpi_y = ctypes.windll.gdi32.GetDeviceCaps(hdc, 90)  # LOGPIXELSY
                return (dpi_x, dpi_y)
            finally:
                user32.ReleaseDC(hwnd, hdc)
                
    except Exception as e:
        get_logger().warning(f"获取窗口 DPI 失败: {e}")
        
    return (STANDARD_DPI, STANDARD_DPI)


def get_dpi_for_monitor(hmonitor: int) -> Tuple[int, int]:
    """
    获取显示器的 DPI 值
    
    Args:
        hmonitor: 显示器句柄
        
    Returns:
        Tuple[int, int]: (dpi_x, dpi_y)，失败返回 (96, 96)
    """
    try:
        if hasattr(shcore, 'GetDpiForMonitor'):
            dpi_x = wintypes.UINT()
            dpi_y = wintypes.UINT()
            if shcore.GetDpiForMonitor(hmonitor, MDT_EFFECTIVE_DPI,
                                     ctypes.byref(dpi_x), ctypes.byref(dpi_y)) == 0:
                return (dpi_x.value, dpi_y.value)
    except Exception as e:
        get_logger().warning(f"获取显示器 DPI 失败: {e}")
        
    return (STANDARD_DPI, STANDARD_DPI)


def get_system_dpi() -> Tuple[int, int]:
    """
    获取系统 DPI 值
    
    Returns:
        Tuple[int, int]: (dpi_x, dpi_y)
    """
    try:
        hdc = user32.GetDC(0)
        if hdc:
            try:
                dpi_x = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                dpi_y = ctypes.windll.gdi32.GetDeviceCaps(hdc, 90)  # LOGPIXELSY
                return (dpi_x, dpi_y)
            finally:
                user32.ReleaseDC(0, hdc)
    except Exception:
        pass
        
    return (STANDARD_DPI, STANDARD_DPI)


def pixels_to_dip(pixels: int, dpi: int) -> int:
    """
    像素转换为 DIP (Device Independent Pixels)
    
    Args:
        pixels: 像素值
        dpi: DPI 值
        
    Returns:
        int: DIP 值
    """
    return round(pixels * STANDARD_DPI / dpi)


def dip_to_pixels(dip: int, dpi: int) -> int:
    """
    DIP 转换为像素
    
    Args:
        dip: DIP 值
        dpi: DPI 值
        
    Returns:
        int: 像素值
    """
    return round(dip * dpi / STANDARD_DPI)


def convert_point_to_dip(x: int, y: int, hwnd: int) -> Tuple[int, int]:
    """
    将屏幕像素坐标转换为 DIP 坐标
    
    Args:
        x, y: 屏幕像素坐标
        hwnd: 参考窗口句柄
        
    Returns:
        Tuple[int, int]: DIP 坐标
    """
    dpi_x, dpi_y = get_dpi_for_window(hwnd)
    return (pixels_to_dip(x, dpi_x), pixels_to_dip(y, dpi_y))


def convert_point_to_pixels(x: int, y: int, hwnd: int) -> Tuple[int, int]:
    """
    将 DIP 坐标转换为屏幕像素坐标
    
    Args:
        x, y: DIP 坐标
        hwnd: 参考窗口句柄
        
    Returns:
        Tuple[int, int]: 屏幕像素坐标
    """
    dpi_x, dpi_y = get_dpi_for_window(hwnd)
    return (dip_to_pixels(x, dpi_x), dip_to_pixels(y, dpi_y))


def get_scaling_factor(hwnd: int) -> Tuple[float, float]:
    """
    获取窗口的缩放因子
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        Tuple[float, float]: (scale_x, scale_y)
    """
    dpi_x, dpi_y = get_dpi_for_window(hwnd)
    return (dpi_x / STANDARD_DPI, dpi_y / STANDARD_DPI)


def logical_to_physical_point(hwnd: int, x: int, y: int) -> Tuple[int, int]:
    """
    逻辑坐标转物理坐标（考虑 DPI 缩放）
    
    Args:
        hwnd: 窗口句柄
        x, y: 逻辑坐标
        
    Returns:
        Tuple[int, int]: 物理坐标
    """
    try:
        if hasattr(user32, 'LogicalToPhysicalPointForPerMonitorDPI'):
            point = POINT(x, y)
            if user32.LogicalToPhysicalPointForPerMonitorDPI(hwnd, ctypes.byref(point)):
                return (point.x, point.y)
    except Exception:
        pass
        
    # 回退到手动计算
    scale_x, scale_y = get_scaling_factor(hwnd)
    return (round(x * scale_x), round(y * scale_y))


def physical_to_logical_point(hwnd: int, x: int, y: int) -> Tuple[int, int]:
    """
    物理坐标转逻辑坐标（考虑 DPI 缩放）
    
    Args:
        hwnd: 窗口句柄
        x, y: 物理坐标
        
    Returns:
        Tuple[int, int]: 逻辑坐标
    """
    try:
        if hasattr(user32, 'PhysicalToLogicalPointForPerMonitorDPI'):
            point = POINT(x, y)
            if user32.PhysicalToLogicalPointForPerMonitorDPI(hwnd, ctypes.byref(point)):
                return (point.x, point.y)
    except Exception:
        pass
        
    # 回退到手动计算
    scale_x, scale_y = get_scaling_factor(hwnd)
    return (round(x / scale_x), round(y / scale_y))


def get_dpi_info_summary() -> dict:
    """
    获取 DPI 信息摘要，用于调试
    
    Returns:
        dict: DPI 信息摘要
    """
    system_dpi = get_system_dpi()
    
    # 获取当前进程的 DPI 感知级别
    awareness = "未知"
    try:
        if hasattr(user32, 'GetProcessDpiAwarenessContext'):
            context = user32.GetProcessDpiAwarenessContext(kernel32.GetCurrentProcess())
            if context == DPI_AWARENESS_CONTEXT_UNAWARE:
                awareness = "不感知"
            elif context == DPI_AWARENESS_CONTEXT_SYSTEM_AWARE:
                awareness = "系统感知"
            elif context == DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE:
                awareness = "Per Monitor V1"
            elif context == DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2:
                awareness = "Per Monitor V2"
    except Exception:
        pass
        
    return {
        'system_dpi': system_dpi,
        'system_scaling': (system_dpi[0] / STANDARD_DPI, system_dpi[1] / STANDARD_DPI),
        'dpi_awareness': awareness,
        'standard_dpi': STANDARD_DPI
    }
