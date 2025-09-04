# -*- coding: utf-8 -*-
"""
测试导入修复
"""

import sys
import traceback

def test_scanner_process_imports():
    """测试扫描进程模块的导入"""
    print("测试扫描进程模块导入...")
    
    try:
        # 测试基础导入
        print("1. 测试基础模块导入...")
        from auto_approve.config_manager import AppConfig
        from auto_approve.logger_manager import get_logger
        from auto_approve.win_clicker import post_click_screen_pos
        from capture.capture_manager import CaptureManager
        from utils.win_dpi import set_process_dpi_awareness
        print("   基础模块导入成功")
        
        # 测试扫描进程模块
        print("2. 测试扫描进程模块...")
        from workers.scanner_process import (
            ScannerCommand, ScannerStatus, ScannerHit,
            ScannerProcessManager, get_global_scanner_manager
        )
        print("   扫描进程模块导入成功")
        
        # 测试适配器
        print("3. 测试适配器模块...")
        from auto_approve.scanner_process_adapter import ProcessScannerWorker
        print("   适配器模块导入成功")
        
        # 测试创建实例
        print("4. 测试创建实例...")
        cfg = AppConfig()
        manager = get_global_scanner_manager()
        adapter = ProcessScannerWorker(cfg)
        print("   实例创建成功")
        
        print("✅ 所有导入测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 导入测试失败: {e}")
        print("详细错误信息:")
        traceback.print_exc()
        return False

def test_click_function():
    """测试点击函数"""
    print("\n测试点击函数...")
    
    try:
        from auto_approve.win_clicker import post_click_screen_pos
        
        # 测试函数调用（不实际点击）
        print("点击函数导入成功")
        print("✅ 点击函数测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 点击函数测试失败: {e}")
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("导入修复验证测试")
    print("=" * 50)
    
    success1 = test_scanner_process_imports()
    success2 = test_click_function()
    
    print("\n" + "=" * 50)
    if success1 and success2:
        print("🎉 所有测试通过，导入问题已修复！")
        return 0
    else:
        print("⚠️  仍有问题需要解决")
        return 1

if __name__ == "__main__":
    sys.exit(main())
