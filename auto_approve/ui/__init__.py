# -*- coding: utf-8 -*-
"""
用户界面模块

包含所有UI相关组件：
- 设置对话框
- 屏幕列表对话框
- WGC预览对话框
- 窗口句柄选择器
- UI增强和优化
"""

# 为了保持向后兼容性，重新导出UI类
try:
    from ..settings_dialog import SettingsDialog
    from ..screen_list_dialog import show_screen_list_dialog
    from ..wgc_preview_dialog import WGCPreviewDialog
    from ..hwnd_picker import HwndPicker
    from ..menu_icons import create_menu_icon
    from ..ui_enhancements import UIEnhancementManager, enhance_widget
    from ..ui_optimizer import TrayMenuOptimizer, get_performance_throttler
except ImportError:
    # 如果文件还没有移动，使用原始导入
    pass

__all__ = [
    'SettingsDialog', 'show_screen_list_dialog', 'WGCPreviewDialog',
    'HwndPicker', 'create_menu_icon', 'UIEnhancementManager', 'enhance_widget',
    'TrayMenuOptimizer', 'get_performance_throttler'
]
