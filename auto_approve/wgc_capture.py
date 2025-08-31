# -*- coding: utf-8 -*-
"""
Windows 窗口级截屏后端（WGC优先，PrintWindow回退）：
- 首选 Windows Graphics Capture 对指定 HWND 抓取 BGRA 帧；
- 低拷贝转换为 numpy(BGR) 供 OpenCV 使用；
- 可配置抓帧 FPS 上限与超时；
- 处理最小化窗口：IsIconic→ShowWindow(hwnd, SW_SHOWNOACTIVATE) 恢复但不激活；
- 回退链路：WGC → PrintWindow → 调用方可继续回退到屏幕截取；
- 提供辅助函数：根据标题查找窗口、判断是否 Electron/Chromium 进程。
"""
from __future__ import annotations
import os
import time
import threading
import ctypes
from ctypes import wintypes
from typing import Optional, Any

import numpy as np
import cv2

from auto_approve.logger_manager import get_logger


# ------------ Windows 常量与API ------------
SW_SHOWNOACTIVATE = 4
SW_MINIMIZE = 6
SW_RESTORE = 9

PW_RENDERFULLCONTENT = 0x00000002

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)

user32.IsIconic.restype = wintypes.BOOL
user32.IsIconic.argtypes = [wintypes.HWND]

user32.ShowWindow.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
try:
    # 尝试绑定异步版本，避免前台限制导致阻塞
    user32.ShowWindowAsync.restype = wintypes.BOOL
    user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
except Exception:
    user32.ShowWindowAsync = None  # 兼容无该符号的环境

user32.GetWindowRect.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(ctypes.wintypes.RECT)]

user32.PrintWindow.restype = wintypes.BOOL
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]

# SetWindowPos 兜底：不激活显示窗口
user32.SetWindowPos.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]

HWND_TOP = wintypes.HWND(0)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]

user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]

user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

psapi.GetModuleFileNameExW.restype = wintypes.DWORD
psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]

kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD)
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ('bmiHeader', BITMAPINFOHEADER),
        ('bmiColors', wintypes.DWORD * 3)
    ]


gdi32.GetDIBits.restype = ctypes.c_int
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                            ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT]


# ------------ WGC 可用性检测 ------------
try:
    import windows_capture  # windows-capture-python
    WGC_AVAILABLE = True
except Exception:
    windows_capture = None
    WGC_AVAILABLE = False


class WGCCaptureBackend:
    """WGC 后端：对指定 HWND 抓取帧，输出 BGR 的 numpy 数组。"""

    def __init__(self, hwnd: int, fps_max: int = 30, timeout_ms: int = 5000):
        self.hwnd = hwnd
        self.fps_max = max(1, min(int(fps_max), 60))
        self.timeout_ms = max(500, int(timeout_ms))
        self.frame_interval = 1.0 / self.fps_max
        self._logger = get_logger()

        self._session = None
        self._last_frame_t = 0.0
        self._lock = threading.Lock()
        self._latest: Optional[np.ndarray] = None
        self._evt = threading.Event()

        self._init_session()

    def _init_session(self) -> bool:
        """初始化 WGC 捕获会话。"""
        if not WGC_AVAILABLE:
            self._logger.warning("WGC库不可用，跳过WGC初始化")
            return False
        try:
            if not hasattr(windows_capture, 'WindowsCapture'):
                self._logger.error("windows_capture 缺少 WindowsCapture 类")
                return False
            self._session = windows_capture.WindowsCapture()
            # 设定目标 HWND
            if hasattr(self._session, 'set_hwnd'):
                self._session.set_hwnd(self.hwnd)
            else:
                setattr(self._session, 'hwnd', self.hwnd)
            # 回调（CreateFreeThreaded池回调由库内部处理）
            if hasattr(self._session, 'on_frame_arrived'):
                self._session.on_frame_arrived = self._on_frame
            if hasattr(self._session, 'on_closed'):
                self._session.on_closed = lambda: self._logger.info("WGC会话已关闭")
            self._logger.info("WGC会话初始化成功")
            return True
        except Exception as e:
            self._logger.error(f"WGC 初始化失败: {e}")
            return False

    def _on_frame(self, frame: Any) -> None:
        """帧到达回调：限制FPS并转换为BGR。"""
        now = time.monotonic()
        if now - self._last_frame_t < self.frame_interval:
            return
        try:
            with self._lock:
                if hasattr(frame, 'buffer') and hasattr(frame, 'width') and hasattr(frame, 'height'):
                    size = frame.width * frame.height * 4
                    arr = np.frombuffer(frame.buffer, dtype=np.uint8)
                    if arr.size >= size:
                        bgra = arr[:size].reshape((frame.height, frame.width, 4))
                        bgr = cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
                        self._latest = bgr.copy()
                        self._last_frame_t = now
                        self._evt.set()
        except Exception as e:
            self._logger.error(f"WGC帧处理失败: {e}")

    def start(self) -> bool:
        """启动捕获。"""
        if not self._session:
            return False
        try:
            self._session.start()
            self._logger.info("WGC 捕获已启动")
            return True
        except Exception as e:
            self._logger.error(f"WGC 启动失败: {e}")
            return False

    def stop(self) -> None:
        """停止捕获。"""
        if self._session:
            try:
                self._session.stop()
            except Exception:
                pass

    def capture_frame(self) -> Optional[np.ndarray]:
        """同步获取一帧（超时受限）。"""
        if not self._session:
            return None
        # 优先回调用途，回退直接拉帧
        if hasattr(self._session, 'on_frame_arrived'):
            if self._evt.wait(self.timeout_ms / 1000.0):
                with self._lock:
                    if self._latest is not None:
                        img = self._latest.copy()
                        self._evt.clear()
                        return img
            return None
        # 直接方法回退
        try:
            get_fn = None
            if hasattr(self._session, 'capture_frame'):
                get_fn = self._session.capture_frame
            elif hasattr(self._session, 'get_frame'):
                get_fn = self._session.get_frame
            if get_fn:
                data = get_fn()
                if isinstance(data, np.ndarray):
                    if data.ndim == 3 and data.shape[2] == 4:
                        return cv2.cvtColor(data, cv2.COLOR_BGRA2BGR)
                    return data
                if hasattr(data, 'buffer') and hasattr(data, 'width') and hasattr(data, 'height'):
                    size = data.width * data.height * 4
                    arr = np.frombuffer(data.buffer, dtype=np.uint8)
                    if arr.size >= size:
                        bgra = arr[:size].reshape((data.height, data.width, 4))
                        return cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            self._logger.error(f"WGC直接拉帧失败: {e}")
        return None

    def __del__(self):
        self.stop()


class PrintWindowBackend:
    """PrintWindow 回退：渲染窗口内容到位图，再拷贝到 numpy。"""
    def __init__(self, hwnd: int):
        self.hwnd = hwnd
        self._logger = get_logger()

    def capture_frame(self) -> Optional[np.ndarray]:
        """捕获一帧（BGR）。"""
        try:
            rect = wintypes.RECT()
            if not user32.GetWindowRect(self.hwnd, ctypes.byref(rect)):
                return None
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w <= 0 or h <= 0:
                return None

            hdc = user32.GetDC(self.hwnd)
            if not hdc:
                return None
            try:
                mdc = gdi32.CreateCompatibleDC(hdc)
                if not mdc:
                    return None
                try:
                    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
                    if not bmp:
                        return None
                    try:
                        old = gdi32.SelectObject(mdc, bmp)
                        # PW_RENDERFULLCONTENT：尽量渲染完整内容
                        ok = user32.PrintWindow(self.hwnd, mdc, PW_RENDERFULLCONTENT)
                        # 读出位图数据（24-bit BGR）
                        bi = BITMAPINFO()
                        bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                        bi.bmiHeader.biWidth = w
                        bi.bmiHeader.biHeight = -h  # top-down
                        bi.bmiHeader.biPlanes = 1
                        bi.bmiHeader.biBitCount = 24
                        bi.bmiHeader.biCompression = 0
                        buf = (ctypes.c_ubyte * (w * h * 3))()
                        if ok and gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0):
                            arr = np.frombuffer(buf, dtype=np.uint8).reshape((h, w, 3))
                            return arr
                        gdi32.SelectObject(mdc, old)
                    finally:
                        gdi32.DeleteObject(bmp)
                finally:
                    gdi32.DeleteDC(mdc)
            finally:
                user32.ReleaseDC(self.hwnd, hdc)
        except Exception as e:
            self._logger.error(f"PrintWindow 捕获失败: {e}")
        return None


class WindowCaptureManager:
    """窗口捕获管理器：封装 WGC+PrintWindow，处理最小化不激活恢复。"""
    def __init__(self, target_hwnd: Optional[int] = None, fps_max: int = 30,
                 timeout_ms: int = 5000, restore_minimized: bool = True):
        self.target_hwnd = target_hwnd or 0
        self.fps_max = max(1, min(int(fps_max), 60))
        self.timeout_ms = max(500, int(timeout_ms))
        self.restore_minimized = bool(restore_minimized)
        self._logger = get_logger()

        self._wgc: Optional[WGCCaptureBackend] = None
        self._pw: Optional[PrintWindowBackend] = None
        self._was_minimized = False

        if self.target_hwnd:
            self._init_backends()

    def _init_backends(self) -> None:
        """初始化两种后端。"""
        # WGC 优先
        if WGC_AVAILABLE:
            try:
                self._wgc = WGCCaptureBackend(self.target_hwnd, self.fps_max, self.timeout_ms)
                if not self._wgc.start():
                    self._logger.warning("WGC 启动失败，将尝试PrintWindow")
                    self._wgc = None
            except Exception as e:
                self._logger.warning(f"WGC 初始化失败: {e}")
                self._wgc = None
        # PrintWindow 兜底
        try:
            self._pw = PrintWindowBackend(self.target_hwnd)
        except Exception as e:
            self._logger.error(f"PrintWindow 初始化失败: {e}")
            self._pw = None

    def _handle_minimized(self) -> bool:
        """如窗口最小化则在后台恢复但不激活。
        恢复顺序：ShowWindowAsync(SW_SHOWNOACTIVATE) → ShowWindow(SW_SHOWNOACTIVATE) →
        SetWindowPos(不激活显示) → ShowWindow(SW_RESTORE)。
        """
        if not self.restore_minimized or not self.target_hwnd:
            return True
        try:
            if user32.IsIconic(self.target_hwnd):
                self._was_minimized = True
                ok = False
                # 1) 异步显示但不激活，避免前台限制
                try:
                    if getattr(user32, 'ShowWindowAsync', None):
                        ok = bool(user32.ShowWindowAsync(self.target_hwnd, SW_SHOWNOACTIVATE))
                except Exception:
                    ok = False
                # 2) 同步不激活显示
                if not ok:
                    try:
                        ok = bool(user32.ShowWindow(self.target_hwnd, SW_SHOWNOACTIVATE))
                    except Exception:
                        ok = False
                # 3) SetWindowPos 不激活显示（不改变大小/位置/层级）
                if not ok:
                    try:
                        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW
                        ok = bool(user32.SetWindowPos(self.target_hwnd, HWND_TOP, 0, 0, 0, 0, flags))
                    except Exception:
                        ok = False
                # 4) 最后兜底：完全恢复（可能会激活）
                if not ok:
                    try:
                        ok = bool(user32.ShowWindow(self.target_hwnd, SW_RESTORE))
                    except Exception:
                        ok = False
                if not ok:
                    self._logger.warning("恢复最小化窗口失败（多方案均未成功）")
                    return False
                # 给DWM合成器一点时间完成可见性更新，避免空帧
                time.sleep(0.12)
                return True
            return True
        except Exception as e:
            self._logger.error(f"处理最小化失败: {e}")
            return False

    def _re_minimize(self) -> None:
        """如需，抓帧后重新最小化。"""
        if self._was_minimized and self.target_hwnd:
            try:
                user32.ShowWindow(self.target_hwnd, SW_MINIMIZE)
            except Exception:
                pass
            self._was_minimized = False

    def capture_frame(self, restore_after_capture: bool = False) -> Optional[np.ndarray]:
        """抓取窗口帧，返回BGR图像。"""
        if not self.target_hwnd:
            self._logger.error("未设置目标HWND")
            return None
        if not self._handle_minimized():
            return None

        img: Optional[np.ndarray] = None
        # 参考备用实现：优先尝试 PrintWindow（部分场景更稳定），再回退 WGC
        if self._pw:
            img = self._pw.capture_frame()
        if img is None and self._wgc:
            img = self._wgc.capture_frame()

        if restore_after_capture:
            self._re_minimize()
        return img

    def set_target_hwnd(self, hwnd: int) -> None:
        """切换目标窗口。"""
        if hwnd == self.target_hwnd:
            return
        self.cleanup()
        self.target_hwnd = hwnd or 0
        if self.target_hwnd:
            self._init_backends()

    def cleanup(self) -> None:
        """释放资源。"""
        if self._wgc:
            self._wgc.stop()
        self._wgc = None
        self._pw = None
        if self._was_minimized:
            self._re_minimize()

    def __del__(self):
        self.cleanup()


def find_window_by_title(title: str, partial_match: bool = True) -> Optional[int]:
    """根据标题查找窗口HWND。"""
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            wt = buf.value
            if partial_match:
                if title.lower() in wt.lower():
                    found.append(hwnd)
                    return False
            else:
                if title.lower() == wt.lower():
                    found.append(hwnd)
                    return False
            return True
        except Exception:
            return True

    user32.EnumWindows(enum_proc, 0)
    return found[0] if found else None


def is_electron_process(hwnd: int) -> bool:
    """简单判定窗口是否 Electron/Chromium 进程。"""
    try:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return False
        hproc = kernel32.OpenProcess(0x0400, False, pid.value)  # PROCESS_QUERY_INFORMATION
        if not hproc:
            return False
        try:
            buf = ctypes.create_unicode_buffer(260)
            if psapi.GetModuleFileNameExW(hproc, None, buf, 260):
                exe = os.path.basename(buf.value).lower()
                names = ['electron.exe', 'code.exe', 'discord.exe', 'slack.exe',
                         'chrome.exe', 'msedge.exe', 'whatsapp.exe', 'spotify.exe']
                return any(n in exe for n in names)
        finally:
            kernel32.CloseHandle(hproc)
    except Exception:
        return False
    return False
