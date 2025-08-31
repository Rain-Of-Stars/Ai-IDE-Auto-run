# -*- coding: utf-8 -*-
"""Windows 无感点击工具：
- 在不移动系统鼠标、不打断当前键盘输入的情况下，向目标窗口发送鼠标按下/抬起消息。
- 采用 PostMessage 发送 WM_LBUTTONDOWN/WM_LBUTTONUP 到对应窗口的客户端坐标。
- 通过 WindowFromPoint/ChildWindowFromPointEx 定位屏幕坐标对应的最深子窗口。
- 增强多屏幕支持：坐标验证、窗口查找优化、调试模式。
注意：部分高权限/特殊窗口可能拦截消息，这种情况将不会进行真实点击以避免干扰。
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import logging
from typing import Optional, Tuple

from auto_approve.logger_manager import get_logger

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)

# 常量定义
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
CWP_SKIPINVISIBLE = 0x0001
CWP_SKIPDISABLED = 0x0002
CWP_SKIPTRANSPARENT = 0x0004

# 结构体与函数签名
class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

class RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

user32.WindowFromPoint.restype = wintypes.HWND
user32.WindowFromPoint.argtypes = [POINT]

user32.ChildWindowFromPointEx.restype = wintypes.HWND
user32.ChildWindowFromPointEx.argtypes = [wintypes.HWND, POINT, wintypes.UINT]

user32.ScreenToClient.restype = wintypes.BOOL
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]

user32.PostMessageW.restype = wintypes.BOOL
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

user32.IsWindow.restype = wintypes.BOOL
user32.IsWindow.argtypes = [wintypes.HWND]

user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]

user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

user32.GetClassNameW.restype = ctypes.c_int
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]

user32.IsWindowEnabled.restype = wintypes.BOOL
user32.IsWindowEnabled.argtypes = [wintypes.HWND]

user32.GetParent.restype = wintypes.HWND
user32.GetParent.argtypes = [wintypes.HWND]

user32.MonitorFromPoint.restype = wintypes.HANDLE
user32.MonitorFromPoint.argtypes = [POINT, wintypes.DWORD]

# 监视器相关常量
MONITOR_DEFAULTTONULL = 0x00000000
MONITOR_DEFAULTTOPRIMARY = 0x00000001
MONITOR_DEFAULTTONEAREST = 0x00000002

# 发送消息保护：SendMessageTimeout
SMTO_NORMAL = 0x0000
SMTO_BLOCK = 0x0001
SMTO_ABORTIFHUNG = 0x0002
SMTO_NOTIMEOUTIFNOTHUNG = 0x0008

LRESULT = ctypes.c_ssize_t
user32.SendMessageTimeoutW.restype = LRESULT
user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(wintypes.DWORD)
]

# 前台窗口/进程名
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetForegroundWindow.argtypes = []
user32.GetClientRect = user32.GetClientRect
user32.GetClientRect.restype = wintypes.BOOL
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.ClientToScreen.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


# 全局logger实例
_logger = None

def _get_logger():
    """获取logger实例。"""
    global _logger
    if _logger is None:
        _logger = get_logger()
    return _logger

def _make_lparam(x: int, y: int) -> int:
    # 生成 LPARAM：低位为 x，高位为 y（均为无符号16位）
    return (y & 0xFFFF) << 16 | (x & 0xFFFF)

def _get_process_name_by_pid(pid: int) -> str:
    """通过PID获取进程可执行名（基名）。"""
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(len(buf))
        ok = kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
        if not ok:
            return ""
        path = buf.value
        return path.split("\\")[-1]
    finally:
        kernel32.CloseHandle(h)

def get_foreground_window_info() -> dict:
    """获取当前前台窗口的关键信息：hwnd、进程名、客户区屏幕矩形。"""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"valid": False}
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    pname = _get_process_name_by_pid(int(pid.value))
    # 取客户区矩形(客户端坐标)，转换为屏幕坐标
    rc = RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rc)):
        return {"valid": False}
    lt = POINT(rc.left, rc.top)
    rb = POINT(rc.right, rc.bottom)
    user32.ClientToScreen(hwnd, ctypes.byref(lt))
    user32.ClientToScreen(hwnd, ctypes.byref(rb))
    rect = {"left": lt.x, "top": lt.y, "right": rb.x, "bottom": rb.y,
            "width": max(0, rb.x - lt.x), "height": max(0, rb.y - lt.y)}
    return {"valid": True, "hwnd": hwnd, "process": pname, "client_rect": rect}

# WinEventHook：前台窗口变化
WinEventProcType = ctypes.WINFUNCTYPE(
    None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
    wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD
)

EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002

_win_event_hook_handle = None
_win_event_callback = None

def start_foreground_watcher(on_change):
    """启动前台窗口事件监听。on_change(hwnd:int, process:str) 被调用。"""
    global _win_event_hook_handle, _win_event_callback
    def _cb(hWinEventHook, event, hwnd, idObject, idChild, idEventThread, dwmsEventTime):
        try:
            if event != EVENT_SYSTEM_FOREGROUND or not hwnd:
                return
            pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            pname = _get_process_name_by_pid(int(pid.value))
            on_change(int(hwnd), pname)
        except Exception:
            pass
    _win_event_callback = WinEventProcType(_cb)
    _win_event_hook_handle = user32.SetWinEventHook(
        EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND,
        None, _win_event_callback,
        0, 0,
        WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS
    )
    return _win_event_hook_handle

def stop_foreground_watcher():
    """停止前台窗口事件监听。"""
    global _win_event_hook_handle, _win_event_callback
    if _win_event_hook_handle:
        try:
            user32.UnhookWinEvent(_win_event_hook_handle)
        except Exception:
            pass
    _win_event_hook_handle = None
    _win_event_callback = None

def _get_window_info(hwnd: int, debug: bool = False) -> dict:
    """获取窗口详细信息用于调试。"""
    if not hwnd or not user32.IsWindow(hwnd):
        return {"valid": False}
    
    # 获取窗口标题
    title_buffer = ctypes.create_unicode_buffer(256)
    title_len = user32.GetWindowTextW(hwnd, title_buffer, 256)
    title = title_buffer.value if title_len > 0 else ""
    
    # 获取窗口类名
    class_buffer = ctypes.create_unicode_buffer(256)
    class_len = user32.GetClassNameW(hwnd, class_buffer, 256)
    class_name = class_buffer.value if class_len > 0 else ""
    
    # 获取窗口矩形
    rect = RECT()
    has_rect = user32.GetWindowRect(hwnd, ctypes.byref(rect))
    
    info = {
        "valid": True,
        "hwnd": hwnd,
        "title": title,
        "class_name": class_name,
        "visible": bool(user32.IsWindowVisible(hwnd)),
        "enabled": bool(user32.IsWindowEnabled(hwnd)),
        "parent": user32.GetParent(hwnd)
    }
    
    if has_rect:
        info["rect"] = {
            "left": rect.left,
            "top": rect.top,
            "right": rect.right,
            "bottom": rect.bottom,
            "width": rect.right - rect.left,
            "height": rect.bottom - rect.top
        }
    
    return info

def _validate_screen_coordinates(sx: int, sy: int, debug: bool = False) -> bool:
    """验证屏幕坐标是否在有效的监视器范围内。"""
    pt = POINT(sx, sy)
    monitor = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONULL)
    
    if not monitor:
        if debug:
            _get_logger().warning(f"坐标({sx},{sy})不在任何监视器范围内")
        return False
    
    if debug:
        _get_logger().info(f"坐标({sx},{sy})位于监视器{monitor}")
    
    return True


def _deep_child_from_point(hwnd: int, sx: int, sy: int, debug: bool = False, max_depth: int = 10) -> int:
    """递归查找屏幕坐标 (sx, sy) 对应的最深子窗口。
    
    Args:
        hwnd: 起始窗口句柄
        sx, sy: 屏幕坐标
        debug: 是否启用调试输出
        max_depth: 最大递归深度，防止无限递归
    
    Returns:
        最深子窗口的句柄
    """
    if max_depth <= 0:
        if debug:
            _get_logger().warning(f"达到最大递归深度，停止查找子窗口")
        return hwnd if hwnd else 0
    
    pt = POINT(sx, sy)
    parent = user32.WindowFromPoint(pt)
    if not parent or not user32.IsWindow(parent):
        if debug:
            _get_logger().warning(f"在坐标({sx},{sy})处未找到有效窗口")
        return 0
    
    if debug:
        window_info = _get_window_info(parent, debug=False)
        _get_logger().debug(f"查找子窗口: hwnd={parent}, 标题='{window_info.get('title', '')}', 类名='{window_info.get('class_name', '')}', 坐标=({sx},{sy})")
    
    # 尝试获取子窗口
    lpt = POINT(sx, sy)
    # ChildWindowFromPointEx 需要父窗口客户区坐标，这里将屏幕坐标转换为父窗口客户区坐标
    if not user32.ScreenToClient(parent, ctypes.byref(lpt)):
        if debug:
            _get_logger().warning(f"屏幕坐标转换失败: hwnd={parent}, 坐标=({sx},{sy})")
        return parent
    
    if debug:
        _get_logger().debug(f"客户端坐标: ({lpt.x},{lpt.y})")
    
    child = user32.ChildWindowFromPointEx(parent, lpt,
                                           CWP_SKIPINVISIBLE | CWP_SKIPDISABLED | CWP_SKIPTRANSPARENT)
    
    if child and child != parent:
        if debug:
            child_info = _get_window_info(child, debug=False)
            _get_logger().debug(f"找到子窗口: hwnd={child}, 标题='{child_info.get('title', '')}', 类名='{child_info.get('class_name', '')}')")
        
        # 递归查找更深层的子窗口
        return _deep_child_from_point(child, sx, sy, debug, max_depth - 1)
    else:
        if debug:
            _get_logger().debug(f"未找到子窗口，返回当前窗口: hwnd={parent}")
        return parent


def post_click_screen_pos(sx: int, sy: int, debug: bool = False, enhanced_finding: bool = False, 
                          verify_window: bool = False) -> bool:
    """在屏幕坐标 (sx, sy) 处执行无感点击。
    
    Args:
        sx: 屏幕 X 坐标
        sy: 屏幕 Y 坐标
        debug: 是否启用调试输出
        enhanced_finding: 是否使用增强的窗口查找算法
        verify_window: 是否在点击前验证窗口状态
    
    Returns:
        bool: 点击是否成功发送
    """
    if debug:
        _get_logger().info(f"开始无感点击: 屏幕坐标=({sx},{sy}), 增强查找={enhanced_finding}, 验证窗口={verify_window}")
    
    # 验证屏幕坐标
    if not _validate_screen_coordinates(sx, sy, debug):
        if debug:
            _get_logger().error(f"无效的屏幕坐标: ({sx},{sy})")
        return False
    
    # 获取目标窗口
    if enhanced_finding:
        # 使用增强的窗口查找
        target_hwnd = _enhanced_window_from_point(sx, sy, debug)
    else:
        # 使用标准的窗口查找
        target_hwnd = _deep_child_from_point(0, sx, sy, debug)
    
    if not target_hwnd:
        if debug:
            _get_logger().error(f"在坐标({sx},{sy})处未找到目标窗口")
        return False
    
    if debug:
        window_info = _get_window_info(target_hwnd, debug=False)
        _get_logger().info(f"目标窗口: hwnd={target_hwnd}, 标题='{window_info.get('title', '')}', 类名='{window_info.get('class_name', '')}')")
    
    # 验证窗口状态
    if verify_window:
        if not _verify_window_state(target_hwnd, debug):
            if debug:
                _get_logger().error(f"窗口状态验证失败: hwnd={target_hwnd}")
            return False
    
    # 将屏幕坐标转换为窗口客户端坐标
    pt = POINT(sx, sy)
    if not user32.ScreenToClient(target_hwnd, ctypes.byref(pt)):
        if debug:
            _get_logger().error(f"屏幕坐标转换失败: hwnd={target_hwnd}, 坐标=({sx},{sy})")
        return False
    
    if debug:
        _get_logger().info(f"客户端坐标: ({pt.x},{pt.y})")
    
    # 发送鼠标按下和抬起消息（使用 SendMessageTimeout 防挂死）
    lparam = _make_lparam(pt.x, pt.y)
    if debug:
        _get_logger().info(f"发送点击消息(带超时): lparam=0x{lparam:08x}")
    timeout_ms = 200  # 防止窗口挂起导致卡死
    dw_result = wintypes.DWORD(0)
    r1 = user32.SendMessageTimeoutW(target_hwnd, WM_LBUTTONDOWN, 1, lparam,
                                    SMTO_ABORTIFHUNG, timeout_ms, ctypes.byref(dw_result))
    r2 = user32.SendMessageTimeoutW(target_hwnd, WM_LBUTTONUP, 0, lparam,
                                    SMTO_ABORTIFHUNG, timeout_ms, ctypes.byref(dw_result))
    success = bool(r1 and r2)
    if debug:
        _get_logger().info(f"点击消息发送结果: 按下={bool(r1)}, 抬起={bool(r2)}, 总体={success}")
    return success

# 可选：pywinauto UIA 后端查找控件点击
def try_uia_click_keywords(hwnd: int, keywords: tuple[str, ...] = ("Approve", "Run", "Continue")) -> bool:
    """尝试通过 UIA 查找常见按钮并点击，找不到返回 False。
    若未安装 pywinauto，则直接返回 False。
    """
    try:
        from pywinauto import Application
        from pywinauto.controls.uia_controls import ButtonWrapper
        app = Application(backend='uia').connect(handle=hwnd, timeout=0.5)
        dlg = app.window(handle=hwnd)
        dlg.set_focus()
        # 广度搜索按钮
        for kw in keywords:
            try:
                btn = dlg.child_window(title_re=rf".*{kw}.*", control_type="Button")
                if btn.exists(timeout=0.2):
                    ButtonWrapper(btn.element_info).click_input()
                    return True
            except Exception:
                continue
    except Exception:
        return False
    return False

def _enhanced_window_from_point(sx: int, sy: int, debug: bool = False) -> int:
    """增强的窗口查找算法，尝试多种方法找到最合适的目标窗口。"""
    if debug:
        _get_logger().info(f"使用增强窗口查找算法: 坐标=({sx},{sy})")
    
    # 方法1：标准的WindowFromPoint
    pt = POINT(sx, sy)
    hwnd1 = user32.WindowFromPoint(pt)
    
    if debug and hwnd1:
        info1 = _get_window_info(hwnd1, debug=False)
        _get_logger().debug(f"方法1(WindowFromPoint): hwnd={hwnd1}, 标题='{info1.get('title', '')}', 类名='{info1.get('class_name', '')}')")
    
    # 方法2：深度子窗口查找
    hwnd2 = _deep_child_from_point(0, sx, sy, debug=False)
    
    if debug and hwnd2:
        info2 = _get_window_info(hwnd2, debug=False)
        _get_logger().debug(f"方法2(深度查找): hwnd={hwnd2}, 标题='{info2.get('title', '')}', 类名='{info2.get('class_name', '')}')")
    
    # 选择最佳窗口
    candidates = [hwnd for hwnd in [hwnd1, hwnd2] if hwnd and user32.IsWindow(hwnd)]
    
    if not candidates:
        if debug:
            _get_logger().warning(f"所有方法都未找到有效窗口")
        return 0
    
    # 优先选择可见且启用的窗口
    for hwnd in candidates:
        if user32.IsWindowVisible(hwnd) and user32.IsWindowEnabled(hwnd):
            if debug:
                _get_logger().info(f"选择可见且启用的窗口: hwnd={hwnd}")
            return hwnd
    
    # 如果没有可见且启用的窗口，返回第一个有效窗口
    result = candidates[0]
    if debug:
        _get_logger().info(f"选择第一个有效窗口: hwnd={result}")
    return result

def _verify_window_state(hwnd: int, debug: bool = False) -> bool:
    """验证窗口状态是否适合接收点击消息。"""
    if not hwnd or not user32.IsWindow(hwnd):
        if debug:
            _get_logger().warning(f"窗口句柄无效: hwnd={hwnd}")
        return False
    
    # 检查窗口是否可见
    visible = user32.IsWindowVisible(hwnd)
    # 检查窗口是否启用
    enabled = user32.IsWindowEnabled(hwnd)
    
    if debug:
        window_info = _get_window_info(hwnd, debug=False)
        _get_logger().info(f"窗口状态验证: hwnd={hwnd}, 可见={visible}, 启用={enabled}, 标题='{window_info.get('title', '')}')")
    
    # 窗口必须是启用的，可见性可以放宽要求
    return enabled

def post_click_with_config(sx: int, sy: int, config) -> bool:
    """根据配置执行点击操作。
    
    Args:
        sx: 屏幕 X 坐标
        sy: 屏幕 Y 坐标
        config: 应用配置对象
    
    Returns:
        bool: 点击是否成功
    """
    debug = getattr(config, 'debug_mode', False)
    enhanced_finding = getattr(config, 'enhanced_window_finding', False)
    verify_window = getattr(config, 'verify_window_before_click', False)
    
    return post_click_screen_pos(sx, sy, debug, enhanced_finding, verify_window)
