# -*- coding: utf-8 -*-
"""
自动窗口句柄更新器演示
"""
import sys
import os
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import AppConfig
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater


def demo_auto_hwnd_updater():
    """演示自动窗口句柄更新器"""
    print("自动窗口句柄更新器演示")
    print("=" * 50)
    
    updater = AutoHWNDUpdater()
    
    # 设置配置
    config = AppConfig()
    config.auto_update_hwnd_by_process = True
    config.auto_update_hwnd_interval_ms = 2000  # 2秒更新一次
    config.target_process = "explorer.exe"
    config.process_partial_match = True
    
    print(f"配置信息:")
    print(f"  目标进程: {config.target_process}")
    print(f"  部分匹配: {config.process_partial_match}")
    print(f"  更新间隔: {config.auto_update_hwnd_interval_ms}ms")
    print(f"  自动更新: {config.auto_update_hwnd_by_process}")
    print()
    
    # 设置回调函数
    def on_hwnd_updated(hwnd, process_name):
        print(f"检测到窗口更新: HWND={hwnd}, 进程={os.path.basename(process_name)}")
        
    updater.hwnd_updated.connect(on_hwnd_updated)
    
    # 启动更新器
    print("启动自动窗口句柄更新器...")
    updater.set_config(config)
    updater.start()
    
    print("运行中，按 Ctrl+C 停止...")
    print("-" * 50)
    
    try:
        # 运行一段时间
        for i in range(10):
            time.sleep(1)
            current_hwnd = updater.get_current_hwnd()
            if current_hwnd > 0:
                print(f"当前HWND: {current_hwnd}")
            else:
                print("未找到目标进程窗口")
                
    except KeyboardInterrupt:
        print("用户中断，正在停止...")
        
    finally:
        # 停止更新器
        updater.stop()
        print("自动窗口句柄更新器已停止")


if __name__ == "__main__":
    demo_auto_hwnd_updater()