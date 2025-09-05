# -*- coding: utf-8 -*-
"""
自动窗口句柄更新器最小测试
"""
import sys
import os
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import AppConfig
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater


def test_minimal():
    """最小测试"""
    print("开始最小测试...")
    
    updater = AutoHWNDUpdater()
    
    # 设置配置
    config = AppConfig()
    config.auto_update_hwnd_by_process = True
    config.auto_update_hwnd_interval_ms = 1000
    config.target_process = "explorer.exe"
    config.process_partial_match = True
    
    updater.set_config(config)
    
    # 启动更新器
    updater.start()
    print("更新器已启动")
    
    # 等待2秒
    time.sleep(2)
    
    # 检查当前HWND
    current_hwnd = updater.get_current_hwnd()
    print(f"当前HWND: {current_hwnd}")
    
    # 停止更新器
    updater.stop()
    print("更新器已停止")
    
    return current_hwnd > 0


if __name__ == "__main__":
    success = test_minimal()
    if success:
        print("✓ 最小测试通过 - 成功找到explorer.exe窗口")
    else:
        print("✗ 最小测试失败 - 未找到explorer.exe窗口")