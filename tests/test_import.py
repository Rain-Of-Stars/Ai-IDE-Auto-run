# -*- coding: utf-8 -*-
"""
简单的导入测试
"""

import sys
import traceback

def test_imports():
    """测试导入"""
    print("开始导入测试...")
    
    try:
        print("1. 导入基础模块...")
        from PySide6 import QtWidgets, QtCore
        print("   PySide6 导入成功")
        
        print("2. 导入配置管理器...")
        from auto_approve.config_manager import AppConfig, load_config
        print("   配置管理器导入成功")
        
        print("3. 导入日志管理器...")
        from auto_approve.logger_manager import get_logger, enable_file_logging
        print("   日志管理器导入成功")
        
        print("4. 导入扫描进程模块...")
        from workers.scanner_process import get_global_scanner_manager
        print("   扫描进程模块导入成功")
        
        print("5. 导入适配器...")
        from auto_approve.scanner_process_adapter import ProcessScannerWorker
        print("   适配器导入成功")
        
        print("6. 测试创建配置...")
        cfg = AppConfig()
        print(f"   配置创建成功: {type(cfg)}")
        
        print("7. 测试创建扫描管理器...")
        manager = get_global_scanner_manager()
        print(f"   扫描管理器创建成功: {type(manager)}")
        
        print("所有导入测试通过！")
        return True
        
    except Exception as e:
        print(f"导入测试失败: {e}")
        print("详细错误信息:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
