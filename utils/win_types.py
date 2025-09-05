# -*- coding: utf-8 -*-
"""
统一的Windows API类型定义

集中定义所有Windows API相关的结构体和常量，避免重复定义和冲突
"""

import ctypes
from ctypes import wintypes
from typing import Tuple, Optional


# ==================== 基础结构体 ====================

class POINT(ctypes.Structure):
    """Windows POINT 结构体
    
    表示屏幕或窗口中的一个点的坐标
    """
    _fields_ = [
        ("x", wintypes.LONG), 
        ("y", wintypes.LONG)
    ]
    
    def __init__(self, x: int = 0, y: int = 0):
        super().__init__()
        self.x = x
        self.y = y
    
    def __str__(self) -> str:
        return f"POINT(x={self.x}, y={self.y})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    def to_tuple(self) -> Tuple[int, int]:
        """转换为元组"""
        return (self.x, self.y)
    
    @classmethod
    def from_tuple(cls, point: Tuple[int, int]) -> 'POINT':
        """从元组创建POINT"""
        return cls(point[0], point[1])


class RECT(ctypes.Structure):
    """Windows RECT 结构体
    
    表示矩形区域的坐标
    """
    _fields_ = [
        ("left", wintypes.LONG), 
        ("top", wintypes.LONG),
        ("right", wintypes.LONG), 
        ("bottom", wintypes.LONG)
    ]
    
    def __init__(self, left: int = 0, top: int = 0, right: int = 0, bottom: int = 0):
        super().__init__()
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
    
    def __str__(self) -> str:
        return f"RECT(left={self.left}, top={self.top}, right={self.right}, bottom={self.bottom})"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    @property
    def width(self) -> int:
        """矩形宽度"""
        return self.right - self.left
    
    @property
    def height(self) -> int:
        """矩形高度"""
        return self.bottom - self.top
    
    @property
    def size(self) -> Tuple[int, int]:
        """矩形尺寸 (width, height)"""
        return (self.width, self.height)
    
    @property
    def center(self) -> POINT:
        """矩形中心点"""
        return POINT(
            (self.left + self.right) // 2,
            (self.top + self.bottom) // 2
        )
    
    def contains_point(self, x: int, y: int) -> bool:
        """检查点是否在矩形内"""
        return (self.left <= x <= self.right and 
                self.top <= y <= self.bottom)
    
    def contains_rect(self, other: 'RECT') -> bool:
        """检查是否包含另一个矩形"""
        return (self.left <= other.left and 
                self.top <= other.top and
                self.right >= other.right and 
                self.bottom >= other.bottom)
    
    def intersects(self, other: 'RECT') -> bool:
        """检查是否与另一个矩形相交"""
        return not (self.right < other.left or 
                   other.right < self.left or
                   self.bottom < other.top or 
                   other.bottom < self.top)
    
    def intersection(self, other: 'RECT') -> Optional['RECT']:
        """计算与另一个矩形的交集"""
        if not self.intersects(other):
            return None
        
        return RECT(
            max(self.left, other.left),
            max(self.top, other.top),
            min(self.right, other.right),
            min(self.bottom, other.bottom)
        )
    
    def union(self, other: 'RECT') -> 'RECT':
        """计算与另一个矩形的并集"""
        return RECT(
            min(self.left, other.left),
            min(self.top, other.top),
            max(self.right, other.right),
            max(self.bottom, other.bottom)
        )
    
    def to_tuple(self) -> Tuple[int, int, int, int]:
        """转换为元组 (left, top, right, bottom)"""
        return (self.left, self.top, self.right, self.bottom)
    
    def to_xywh(self) -> Tuple[int, int, int, int]:
        """转换为 (x, y, width, height) 格式"""
        return (self.left, self.top, self.width, self.height)
    
    @classmethod
    def from_tuple(cls, rect: Tuple[int, int, int, int]) -> 'RECT':
        """从元组创建RECT (left, top, right, bottom)"""
        return cls(rect[0], rect[1], rect[2], rect[3])
    
    @classmethod
    def from_xywh(cls, x: int, y: int, width: int, height: int) -> 'RECT':
        """从 (x, y, width, height) 创建RECT"""
        return cls(x, y, x + width, y + height)


# ==================== 扩展结构体 ====================

class SIZE(ctypes.Structure):
    """Windows SIZE 结构体"""
    _fields_ = [
        ("cx", wintypes.LONG),
        ("cy", wintypes.LONG)
    ]
    
    def __init__(self, cx: int = 0, cy: int = 0):
        super().__init__()
        self.cx = cx
        self.cy = cy
    
    def __str__(self) -> str:
        return f"SIZE(cx={self.cx}, cy={self.cy})"
    
    def to_tuple(self) -> Tuple[int, int]:
        """转换为元组"""
        return (self.cx, self.cy)


class WINDOWINFO(ctypes.Structure):
    """Windows WINDOWINFO 结构体"""
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcWindow", RECT),
        ("rcClient", RECT),
        ("dwStyle", wintypes.DWORD),
        ("dwExStyle", wintypes.DWORD),
        ("dwWindowStatus", wintypes.DWORD),
        ("cxWindowBorders", wintypes.UINT),
        ("cyWindowBorders", wintypes.UINT),
        ("atomWindowType", wintypes.ATOM),
        ("wCreatorVersion", wintypes.WORD)
    ]
    
    def __init__(self):
        super().__init__()
        self.cbSize = ctypes.sizeof(self)


# ==================== 常量定义 ====================

# 窗口消息常量
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MOUSEMOVE = 0x0200
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102

# 窗口查找常量
CWP_SKIPINVISIBLE = 0x0001
CWP_SKIPDISABLED = 0x0002
CWP_SKIPTRANSPARENT = 0x0004
CWP_ALL = CWP_SKIPINVISIBLE | CWP_SKIPDISABLED | CWP_SKIPTRANSPARENT

# 窗口显示状态
SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_SHOWMAXIMIZED = 3
SW_SHOWNOACTIVATE = 4
SW_SHOW = 5
SW_MINIMIZE = 6
SW_SHOWMINNOACTIVE = 7
SW_SHOWNA = 8
SW_RESTORE = 9

# DPI感知常量
DPI_AWARENESS_INVALID = -1
DPI_AWARENESS_UNAWARE = 0
DPI_AWARENESS_SYSTEM_AWARE = 1
DPI_AWARENESS_PER_MONITOR_AWARE = 2

# 虚拟键码
VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_CANCEL = 0x03
VK_MBUTTON = 0x04
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_RETURN = 0x0D


# ==================== 便捷函数 ====================

def make_point(x: int, y: int) -> POINT:
    """创建POINT实例"""
    return POINT(x, y)


def make_rect(left: int, top: int, right: int, bottom: int) -> RECT:
    """创建RECT实例"""
    return RECT(left, top, right, bottom)


def make_rect_from_xywh(x: int, y: int, width: int, height: int) -> RECT:
    """从坐标和尺寸创建RECT"""
    return RECT.from_xywh(x, y, width, height)


def make_size(width: int, height: int) -> SIZE:
    """创建SIZE实例"""
    return SIZE(width, height)


def point_in_rect(point: POINT, rect: RECT) -> bool:
    """检查点是否在矩形内"""
    return rect.contains_point(point.x, point.y)


def rects_intersect(rect1: RECT, rect2: RECT) -> bool:
    """检查两个矩形是否相交"""
    return rect1.intersects(rect2)


# ==================== 类型别名 ====================

# 为了兼容性，提供一些常用的类型别名
WinPoint = POINT
WinRect = RECT
WinSize = SIZE
