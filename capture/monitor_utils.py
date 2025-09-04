# -*- coding: utf-8 -*-
"""
显示器枚举和窗口查找工具

提供独立于 mss 的显示器枚举功能，以及增强的窗口查找功能。
完全基于 Windows API 实现，支持 WGC 所需的句柄获取。
"""

from __future__ import annotations
import ctypes
import os
from typing import List, Tuple, Optional, Dict, Any

# Windows API 类型定义
from ctypes import wintypes
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32

try:
    psapi = ctypes.windll.psapi
except AttributeError:
    psapi = None

from auto_approve.logger_manager import get_logger

# Windows API 结构体
class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long), 
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]

class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD)
    ]

# 常量
MONITOR_DEFAULTTOPRIMARY = 0x00000001
MONITOR_DEFAULTTONEAREST = 0x00000002
MONITORINFOF_PRIMARY = 0x00000001


def get_monitor_handles() -> List[int]:
    """
    获取所有显示器句柄列表
    
    Returns:
        List[int]: 显示器句柄 (HMONITOR) 列表
    """
    monitors = []
    
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM)
    def enum_proc(hmonitor, hdc, rect, lparam):
        monitors.append(hmonitor)
        return True
        
    user32.EnumDisplayMonitors(None, None, enum_proc, 0)
    return monitors


def get_monitor_info(hmonitor: int) -> Optional[Dict[str, Any]]:
    """
    获取显示器详细信息
    
    Args:
        hmonitor: 显示器句柄
        
    Returns:
        Dict: 显示器信息，包含坐标、尺寸、是否主显示器等
    """
    try:
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            monitor_rect = info.rcMonitor
            work_rect = info.rcWork
            is_primary = bool(info.dwFlags & MONITORINFOF_PRIMARY)
            
            return {
                'hmonitor': hmonitor,
                'left': monitor_rect.left,
                'top': monitor_rect.top,
                'right': monitor_rect.right,
                'bottom': monitor_rect.bottom,
                'width': monitor_rect.right - monitor_rect.left,
                'height': monitor_rect.bottom - monitor_rect.top,
                'work_left': work_rect.left,
                'work_top': work_rect.top,
                'work_right': work_rect.right,
                'work_bottom': work_rect.bottom,
                'work_width': work_rect.right - work_rect.left,
                'work_height': work_rect.bottom - work_rect.top,
                'is_primary': is_primary
            }
    except Exception as e:
        get_logger().error(f"获取显示器信息失败: {e}")
        
    return None


def get_primary_monitor() -> Optional[int]:
    """
    获取主显示器句柄
    
    Returns:
        int: 主显示器句柄，失败返回 None
    """
    monitors = get_monitor_handles()
    for hmonitor in monitors:
        info = get_monitor_info(hmonitor)
        if info and info['is_primary']:
            return hmonitor
    return None


def get_all_monitors_info() -> List[Dict[str, Any]]:
    """
    获取所有显示器的详细信息
    
    Returns:
        List[Dict]: 显示器信息列表，按主显示器优先排序
    """
    monitors = get_monitor_handles()
    monitor_infos = []
    
    for hmonitor in monitors:
        info = get_monitor_info(hmonitor)
        if info:
            monitor_infos.append(info)
            
    # 主显示器排在前面
    monitor_infos.sort(key=lambda x: not x['is_primary'])
    return monitor_infos


def enum_windows(title_substr: str = "") -> List[Tuple[int, str]]:
    """
    枚举所有可见窗口
    
    Args:
        title_substr: 标题子字符串过滤，空字符串表示不过滤
        
    Returns:
        List[Tuple[int, str]]: (hwnd, title) 元组列表
    """
    windows = []
    title_filter = title_substr.lower() if title_substr else ""
    
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
                
            # 获取窗口标题
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
                
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            
            # 应用过滤器
            if title_filter and title_filter not in title.lower():
                return True
                
            windows.append((hwnd, title))
            
        except Exception:
            pass
            
        return True
        
    user32.EnumWindows(enum_proc, 0)
    return windows


def find_window_by_title(title: str, partial_match: bool = True) -> Optional[int]:
    """
    根据标题查找窗口句柄
    
    Args:
        title: 窗口标题
        partial_match: 是否允许部分匹配
        
    Returns:
        int: 窗口句柄，未找到返回 None
    """
    found = []
    target = title.lower()
    
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
                
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
                
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            window_title = buf.value.lower()
            
            if partial_match:
                if target in window_title:
                    found.append(hwnd)
                    return False  # 找到第一个匹配的就停止
            else:
                if target == window_title:
                    found.append(hwnd)
                    return False
                    
        except Exception:
            pass
            
        return True
        
    user32.EnumWindows(enum_proc, 0)
    return found[0] if found else None


def find_window_by_process(process: str, partial_match: bool = True) -> Optional[int]:
    """
    根据进程名或路径查找窗口句柄
    
    Args:
        process: 进程名（如 Code.exe）或完整路径
        partial_match: 是否允许部分匹配
        
    Returns:
        int: 窗口句柄，未找到返回 None
    """
    if not process or not psapi:
        return None
        
    logger = get_logger()
    target = os.path.normcase(process).replace('/', '\\').lower()
    found_hwnd = 0
    
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, lparam):
        nonlocal found_hwnd
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
                
            # 获取窗口所属进程ID
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return True
                
            # 打开进程获取可执行文件路径
            PROCESS_QUERY_INFORMATION = 0x0400
            PROCESS_VM_READ = 0x0010
            hprocess = kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 
                False, 
                pid.value
            )
            if not hprocess:
                return True
                
            try:
                buf = ctypes.create_unicode_buffer(1024)
                if psapi.GetModuleFileNameExW(hprocess, None, buf, 1024):
                    full_path = os.path.normcase(buf.value).replace('/', '\\')
                    base_name = os.path.basename(full_path)
                    
                    full_lower = full_path.lower()
                    base_lower = base_name.lower()
                    
                    if partial_match:
                        match = (target in full_lower) or (target in base_lower)
                    else:
                        match = (target == full_lower) or (target == base_lower)
                        
                    if match:
                        found_hwnd = hwnd
                        return False  # 停止枚举
                        
            finally:
                kernel32.CloseHandle(hprocess)
                
        except Exception as e:
            logger.debug(f"枚举窗口时跳过 {hwnd}: {e}")
            
        return True
        
    user32.EnumWindows(enum_proc, 0)
    return found_hwnd if found_hwnd else None


def get_window_monitor(hwnd: int) -> Optional[int]:
    """
    获取窗口所在的显示器句柄
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        int: 显示器句柄，失败返回 None
    """
    try:
        hmonitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        return hmonitor if hmonitor else None
    except Exception:
        return None


def get_window_rect(hwnd: int) -> Optional[Dict[str, int]]:
    """
    获取窗口矩形区域
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        Dict: 包含 left, top, right, bottom, width, height 的字典
    """
    try:
        rect = RECT()
        if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return {
                'left': rect.left,
                'top': rect.top,
                'right': rect.right,
                'bottom': rect.bottom,
                'width': rect.right - rect.left,
                'height': rect.bottom - rect.top
            }
    except Exception:
        pass
    return None


def is_window_minimized(hwnd: int) -> bool:
    """检查窗口是否最小化"""
    try:
        return bool(user32.IsIconic(hwnd))
    except Exception:
        return False


def is_electron_process(hwnd: int) -> bool:
    """
    检测窗口是否属于 Electron/Chromium 进程
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        bool: 是否为 Electron 进程
    """
    if not psapi:
        return False
        
    try:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return False
            
        hprocess = kernel32.OpenProcess(0x0400, False, pid.value)  # PROCESS_QUERY_INFORMATION
        if not hprocess:
            return False
            
        try:
            buf = ctypes.create_unicode_buffer(260)
            if psapi.GetModuleFileNameExW(hprocess, None, buf, 260):
                exe_name = os.path.basename(buf.value).lower()
                electron_names = [
                    'electron.exe', 'code.exe', 'discord.exe', 'slack.exe',
                    'chrome.exe', 'msedge.exe', 'whatsapp.exe', 'spotify.exe',
                    'teams.exe', 'figma.exe', 'notion.exe'
                ]
                return any(name in exe_name for name in electron_names)
        finally:
            kernel32.CloseHandle(hprocess)
            
    except Exception:
        pass
        
    return False
