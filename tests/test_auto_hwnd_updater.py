# -*- coding: utf-8 -*-
"""
自动窗口句柄更新器测试
"""
import time
import pytest
from PySide6 import QtCore
from auto_approve.config_manager import AppConfig
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater


class TestAutoHWNDUpdater:
    """测试自动窗口句柄更新器"""
    
    def test_basic_functionality(self, qtbot):
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
        
    def test_hwnd_update_callback(self, qtbot):
        """测试HWND更新回调"""
        updater = AutoHWNDUpdater()
        
        # 设置回调函数
        callback_called = False
        callback_hwnd = 0
        
        def test_callback(hwnd):
            nonlocal callback_called, callback_hwnd
            callback_called = True
            callback_hwnd = hwnd
            
        updater.set_update_callback(test_callback)
        
        # 测试信号连接
        signal_received = False
        signal_hwnd = 0
        signal_process = ""
        
        def on_hwnd_updated(hwnd, process_name):
            nonlocal signal_received, signal_hwnd, signal_process
            signal_received = True
            signal_hwnd = hwnd
            signal_process = process_name
            
        updater.hwnd_updated.connect(on_hwnd_updated)
        
        # 启动更新器
        config = AppConfig()
        config.auto_update_hwnd_by_process = True
        config.auto_update_hwnd_interval_ms = 500
        config.target_process = "explorer.exe"
        config.process_partial_match = True
        
        updater.set_config(config)
        updater.start()
        
        # 等待一段时间让更新器运行
        qtbot.wait(2000)
        
        updater.stop()
        
        # 验证至少找到了一个窗口（explorer.exe应该总是存在）
        current_hwnd = updater.get_current_hwnd()
        assert current_hwnd > 0, "应该能找到explorer.exe的窗口"
        
        # 验证回调和信号被调用（如果找到了窗口）
        if callback_called:
            assert callback_hwnd == current_hwnd
            
        if signal_received:
            assert signal_hwnd == current_hwnd
            assert signal_process == "explorer.exe"
            
    def test_config_change_handling(self, qtbot):
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
        
    def test_invalid_process_handling(self, qtbot):
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
        qtbot.wait(1500)
        
        updater.stop()
        
        # 验证没有找到窗口
        current_hwnd = updater.get_current_hwnd()
        assert current_hwnd == 0, "不应该找到不存在的进程"
        
    def test_process_partial_match(self, qtbot):
        """测试进程部分匹配"""
        updater = AutoHWNDUpdater()
        
        # 使用部分匹配
        config = AppConfig()
        config.auto_update_hwnd_by_process = True
        config.auto_update_hwnd_interval_ms = 500
        config.target_process = "explorer"  # 不包含.exe
        config.process_partial_match = True
        
        updater.set_config(config)
        updater.start()
        
        qtbot.wait(1500)
        
        updater.stop()
        
        # 应该能找到explorer.exe的窗口
        current_hwnd = updater.get_current_hwnd()
        assert current_hwnd > 0, "部分匹配应该能找到explorer.exe的窗口"
        
    def test_process_exact_match(self, qtbot):
        """测试进程精确匹配"""
        updater = AutoHWNDUpdater()
        
        # 使用精确匹配但错误的进程名
        config = AppConfig()
        config.auto_update_hwnd_by_process = True
        config.auto_update_hwnd_interval_ms = 500
        config.target_process = "explorer"  # 不包含.exe
        config.process_partial_match = False  # 精确匹配
        
        updater.set_config(config)
        updater.start()
        
        qtbot.wait(1500)
        
        updater.stop()
        
        # 不应该找到窗口（因为精确匹配要求完全匹配）
        current_hwnd = updater.get_current_hwnd()
        assert current_hwnd == 0, "精确匹配不应该找到explorer（需要explorer.exe）"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])