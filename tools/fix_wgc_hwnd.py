# -*- coding: utf-8 -*-
"""
WGC窗口句柄自动修复工具

当WGC初始化失败时，通常是因为配置文件中的窗口句柄(HWND)已失效。
此工具会自动查找有效的目标窗口并更新配置文件。
"""

import json
import ctypes
import sys
import os
from typing import Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from auto_approve.config_manager import load_config, save_config
from auto_approve.logger_manager import get_logger
from capture.monitor_utils import find_window_by_title, find_window_by_process

user32 = ctypes.windll.user32

def is_hwnd_valid(hwnd: int) -> bool:
    """检查窗口句柄是否有效"""
    return bool(user32.IsWindow(hwnd))

def get_window_title(hwnd: int) -> str:
    """获取窗口标题"""
    if not is_hwnd_valid(hwnd):
        return ""
    title_buffer = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, title_buffer, 256)
    return title_buffer.value

def find_valid_target_window(cfg) -> Optional[int]:
    """根据配置查找有效的目标窗口"""
    logger = get_logger()
    
    # 1. 检查当前配置的HWND是否仍然有效
    current_hwnd = getattr(cfg, 'target_hwnd', 0)
    if current_hwnd > 0 and is_hwnd_valid(current_hwnd):
        logger.info(f"当前配置的HWND {current_hwnd} 仍然有效")
        return current_hwnd
    
    # 2. 按窗口标题查找
    target_title = getattr(cfg, 'target_window_title', '')
    if target_title:
        partial_match = getattr(cfg, 'window_title_partial_match', True)
        hwnd = find_window_by_title(target_title, partial_match)
        if hwnd:
            title = get_window_title(hwnd)
            logger.info(f"按标题'{target_title}'找到窗口: HWND={hwnd}, 标题='{title}'")
            return hwnd
    
    # 3. 按进程名查找
    target_process = getattr(cfg, 'target_process', '')
    if target_process:
        partial_match = getattr(cfg, 'process_partial_match', True)
        hwnd = find_window_by_process(target_process, partial_match)
        if hwnd:
            title = get_window_title(hwnd)
            logger.info(f"按进程'{target_process}'找到窗口: HWND={hwnd}, 标题='{title}'")
            return hwnd
    
    logger.error("未找到有效的目标窗口")
    return None

def fix_wgc_hwnd() -> bool:
    """修复WGC窗口句柄配置"""
    logger = get_logger()
    logger.info("=== 开始WGC窗口句柄修复 ===")
    
    try:
        # 加载当前配置
        cfg = load_config()
        current_hwnd = getattr(cfg, 'target_hwnd', 0)
        
        logger.info(f"当前配置的HWND: {current_hwnd}")
        logger.info(f"目标窗口标题: '{getattr(cfg, 'target_window_title', '')}'")
        logger.info(f"目标进程: '{getattr(cfg, 'target_process', '')}'")
        
        # 检查当前HWND是否有效
        if current_hwnd > 0 and is_hwnd_valid(current_hwnd):
            logger.info("当前HWND有效，无需修复")
            return True
        
        logger.warning(f"当前HWND {current_hwnd} 无效，开始查找新的有效窗口")
        
        # 查找有效的目标窗口
        new_hwnd = find_valid_target_window(cfg)
        if not new_hwnd:
            logger.error("未找到有效的目标窗口，修复失败")
            return False
        
        # 更新配置
        cfg.target_hwnd = new_hwnd
        save_config(cfg)
        
        new_title = get_window_title(new_hwnd)
        logger.info(f"✅ WGC窗口句柄已修复: {current_hwnd} -> {new_hwnd}")
        logger.info(f"新窗口标题: '{new_title}'")
        
        return True
        
    except Exception as e:
        logger.error(f"WGC窗口句柄修复失败: {e}")
        return False

def main():
    """主函数"""
    success = fix_wgc_hwnd()
    if success:
        print("✅ WGC窗口句柄修复成功")
    else:
        print("❌ WGC窗口句柄修复失败")
    return success

if __name__ == "__main__":
    main()
