# -*- coding: utf-8 -*-
"""
Windows系统工具模块

包含Windows平台相关的工具：
- Windows API类型定义
- DPI处理工具
"""

# 导出Windows相关工具
try:
    from .win_types import (
        POINT, RECT, SIZE, WINDOWINFO,
        WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEMOVE,
        CWP_SKIPINVISIBLE, CWP_SKIPDISABLED, CWP_SKIPTRANSPARENT,
        SW_HIDE, SW_SHOWNORMAL, SW_SHOWMAXIMIZED, SW_RESTORE,
        make_point, make_rect, make_rect_from_xywh, make_size,
        point_in_rect, rects_intersect
    )
    from ..win_dpi import set_process_dpi_awareness, get_dpi_info_summary
except ImportError:
    # 如果文件还没有移动，使用原始导入
    pass

__all__ = [
    # 结构体
    'POINT', 'RECT', 'SIZE', 'WINDOWINFO',
    # 常量
    'WM_LBUTTONDOWN', 'WM_LBUTTONUP', 'WM_MOUSEMOVE',
    'CWP_SKIPINVISIBLE', 'CWP_SKIPDISABLED', 'CWP_SKIPTRANSPARENT',
    'SW_HIDE', 'SW_SHOWNORMAL', 'SW_SHOWMAXIMIZED', 'SW_RESTORE',
    # 便捷函数
    'make_point', 'make_rect', 'make_rect_from_xywh', 'make_size',
    'point_in_rect', 'rects_intersect',
    # DPI工具
    'set_process_dpi_awareness', 'get_dpi_info_summary'
]
