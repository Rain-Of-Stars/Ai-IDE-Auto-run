# -*- coding: utf-8 -*-
"""
验证独立扫描进程实现

检查所有组件是否正确实现和集成
"""

import sys
import os
from pathlib import Path

def check_file_exists(file_path: str) -> bool:
    """检查文件是否存在"""
    exists = Path(file_path).exists()
    status = "✓" if exists else "✗"
    print(f"{status} {file_path}")
    return exists

def check_import(module_name: str, class_name: str = None) -> bool:
    """检查模块导入"""
    try:
        module = __import__(module_name, fromlist=[class_name] if class_name else [])
        if class_name:
            getattr(module, class_name)
        print(f"✓ {module_name}" + (f".{class_name}" if class_name else ""))
        return True
    except Exception as e:
        print(f"✗ {module_name}" + (f".{class_name}" if class_name else "") + f" - {e}")
        return False

def main():
    """主验证函数"""
    print("=" * 60)
    print("独立扫描进程实现验证")
    print("=" * 60)
    
    # 1. 检查核心文件
    print("\n1. 检查核心文件:")
    files_ok = True
    files_ok &= check_file_exists("workers/scanner_process.py")
    files_ok &= check_file_exists("auto_approve/scanner_process_adapter.py")
    files_ok &= check_file_exists("main_auto_approve_refactored.py")
    
    # 2. 检查导入
    print("\n2. 检查模块导入:")
    imports_ok = True
    imports_ok &= check_import("workers.scanner_process", "ScannerProcessManager")
    imports_ok &= check_import("workers.scanner_process", "get_global_scanner_manager")
    imports_ok &= check_import("auto_approve.scanner_process_adapter", "ProcessScannerWorker")
    imports_ok &= check_import("auto_approve.scanner_process_adapter", "ScannerProcessAdapter")
    
    # 3. 检查数据结构
    print("\n3. 检查数据结构:")
    data_ok = True
    data_ok &= check_import("workers.scanner_process", "ScannerCommand")
    data_ok &= check_import("workers.scanner_process", "ScannerStatus")
    data_ok &= check_import("workers.scanner_process", "ScannerHit")
    
    # 4. 检查依赖
    print("\n4. 检查依赖模块:")
    deps_ok = True
    deps_ok &= check_import("multiprocessing")
    deps_ok &= check_import("PySide6.QtCore", "QObject")
    deps_ok &= check_import("auto_approve.config_manager", "AppConfig")
    deps_ok &= check_import("auto_approve.logger_manager", "get_logger")
    
    # 5. 功能测试
    print("\n5. 基本功能测试:")
    func_ok = True
    
    try:
        # 测试创建扫描管理器
        from workers.scanner_process import get_global_scanner_manager
        manager = get_global_scanner_manager()
        print("✓ 扫描进程管理器创建成功")
        
        # 测试创建适配器
        from auto_approve.scanner_process_adapter import ProcessScannerWorker
        from auto_approve.config_manager import AppConfig
        cfg = AppConfig()
        adapter = ProcessScannerWorker(cfg)
        print("✓ 扫描进程适配器创建成功")
        
        # 测试数据结构
        from workers.scanner_process import ScannerCommand, ScannerStatus, ScannerHit
        cmd = ScannerCommand(command="test")
        status = ScannerStatus(running=True)
        hit = ScannerHit(score=0.9, x=100, y=200, timestamp=0.0)
        print("✓ 数据结构创建成功")
        
    except Exception as e:
        print(f"✗ 功能测试失败: {e}")
        func_ok = False
    
    # 6. 检查主程序集成
    print("\n6. 检查主程序集成:")
    integration_ok = True
    
    try:
        # 检查主程序是否使用了新的进程版扫描器
        with open("main_auto_approve_refactored.py", "r", encoding="utf-8") as f:
            content = f.read()
            
        if "ProcessScannerWorker" in content:
            print("✓ 主程序已集成进程版扫描器")
        else:
            print("✗ 主程序未集成进程版扫描器")
            integration_ok = False
            
        if "scanner_process_adapter" in content:
            print("✓ 主程序已导入适配器模块")
        else:
            print("✗ 主程序未导入适配器模块")
            integration_ok = False
            
    except Exception as e:
        print(f"✗ 主程序集成检查失败: {e}")
        integration_ok = False
    
    # 总结
    print("\n" + "=" * 60)
    print("验证结果总结:")
    print("=" * 60)
    
    all_ok = files_ok and imports_ok and data_ok and deps_ok and func_ok and integration_ok
    
    print(f"文件检查: {'通过' if files_ok else '失败'}")
    print(f"导入检查: {'通过' if imports_ok else '失败'}")
    print(f"数据结构: {'通过' if data_ok else '失败'}")
    print(f"依赖检查: {'通过' if deps_ok else '失败'}")
    print(f"功能测试: {'通过' if func_ok else '失败'}")
    print(f"集成检查: {'通过' if integration_ok else '失败'}")
    
    print(f"\n总体状态: {'✓ 所有检查通过' if all_ok else '✗ 存在问题'}")
    
    if all_ok:
        print("\n🎉 独立扫描进程实现验证成功！")
        print("现在可以运行主程序体验无卡顿的扫描功能。")
    else:
        print("\n⚠️  发现问题，请检查上述失败项目。")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
