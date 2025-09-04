# -*- coding: utf-8 -*-
"""
最终修复测试
"""

import sys
import traceback

def test_all_imports():
    """测试所有相关模块的导入"""
    print("开始最终修复测试...")
    
    try:
        print("1. 测试基础模块...")
        from auto_approve.config_manager import AppConfig
        from auto_approve.logger_manager import get_logger
        print("   基础模块导入成功")
        
        print("2. 测试点击模块...")
        from auto_approve.win_clicker import post_click_screen_pos
        print("   点击模块导入成功")
        
        print("3. 测试扫描进程模块...")
        from workers.scanner_process import (
            ScannerProcessManager, 
            get_global_scanner_manager,
            ScannerCommand,
            ScannerStatus,
            ScannerHit
        )
        print("   扫描进程模块导入成功")
        
        print("4. 测试适配器模块...")
        from auto_approve.scanner_process_adapter import ProcessScannerWorker
        print("   适配器模块导入成功")
        
        print("5. 测试重构版扫描器...")
        from auto_approve.scanner_worker_refactored import RefactoredScannerWorker
        print("   重构版扫描器导入成功")
        
        print("6. 创建实例测试...")
        cfg = AppConfig()
        manager = get_global_scanner_manager()
        adapter = ProcessScannerWorker(cfg)
        print("   实例创建成功")
        
        print("✅ 所有导入和创建测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        print("详细错误信息:")
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("最终修复验证测试")
    print("=" * 50)
    
    success = test_all_imports()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 修复验证成功！所有导入问题已解决！")
        print("现在可以正常运行主程序了。")
        return 0
    else:
        print("⚠️  仍有问题需要解决")
        return 1

if __name__ == "__main__":
    sys.exit(main())
