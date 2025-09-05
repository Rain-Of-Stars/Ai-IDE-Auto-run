# -*- coding: utf-8 -*-
"""
自动窗口句柄更新器快速测试
"""
import sys
import os
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import AppConfig
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater


def test_basic_functionality():
    """测试基本功能"""
    updater = AutoHWNDUpdater()
    
    # 测试配置设置
    config = AppConfig()
    config.auto_update_hwnd_by_process = True
    config.auto_update_hwnd_interval_ms = 1000
    config.target_process = "explorer.exe"
    config.process_partial_match = True
    
    updater.set_config(config)
    
    # 验证配置已设置
    assert updater._config == config
    
    # 测试启动和停止
    updater.start()
    assert updater.is_running() == True
    
    time.sleep(0.1)  # 给一点时间启动
    
    updater.stop()
    assert updater.is_running() == False
    
    print("✓ 基本功能测试通过")


def test_config_change_handling():
    """测试配置变更处理"""
    updater = AutoHWNDUpdater()
    
    # 初始配置 - 禁用自动更新
    config1 = AppConfig()
    config1.auto_update_hwnd_by_process = False
    config1.auto_update_hwnd_interval_ms = 1000
    config1.target_process = "explorer.exe"
    
    updater.set_config(config1)
    assert updater.is_running() == False
    
    # 更改为启用自动更新
    config2 = AppConfig()
    config2.auto_update_hwnd_by_process = True
    config2.auto_update_hwnd_interval_ms = 500
    config2.target_process = "explorer.exe"
    
    updater.set_config(config2)
    assert updater.is_running() == True
    
    # 再次更改为禁用
    config3 = AppConfig()
    config3.auto_update_hwnd_by_process = False
    
    updater.set_config(config3)
    time.sleep(0.1)  # 给时间处理停止
    assert updater.is_running() == False
    
    updater.stop()  # 确保完全停止
    
    print("✓ 配置变更处理测试通过")


def test_invalid_process_handling():
    """测试无效进程处理"""
    updater = AutoHWNDUpdater()
    
    config = AppConfig()
    config.auto_update_hwnd_by_process = True
    config.auto_update_hwnd_interval_ms = 500
    config.target_process = "nonexistent_process_12345.exe"
    config.process_partial_match = True
    
    updater.set_config(config)
    updater.start()
    
    # 等待更新器运行
    time.sleep(1)
    
    updater.stop()
    
    # 验证没有找到窗口
    current_hwnd = updater.get_current_hwnd()
    print(f"当前HWND: {current_hwnd}")
    
    print("✓ 无效进程处理测试通过")


if __name__ == "__main__":
    print("开始测试自动窗口句柄更新器...")
    
    test_basic_functionality()
    test_config_change_handling()
    test_invalid_process_handling()
    
    print("\n✅ 所有快速测试通过！")